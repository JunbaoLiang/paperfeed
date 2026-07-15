"use client";

import { useCallback, useEffect, useRef } from "react";
import { tracker } from "@/lib/tracker";

/**
 * Per-card impression tracking (spec §10):
 *
 * - visible: fired once when the card is ≥50% visible continuously for ≥1s
 *   (IntersectionObserver threshold 0.5 + a 1s timer canceled on exit).
 * - dwell: measured from abstract expansion until collapse OR the card
 *   leaving the viewport; reported via tracker.recordDwell (max wins,
 *   fired once). If the card re-enters while still expanded, a new
 *   measurement starts — only the longest is sent.
 */
export function useImpressionTracking(impressionId: string) {
  const ref = useRef<HTMLElement | null>(null);
  const visibleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inView = useRef(false);
  const expandedRef = useRef(false);
  const dwellStart = useRef<number | null>(null);
  const unregisterCloser = useRef<(() => void) | null>(null);

  const closeDwell = useCallback(() => {
    if (dwellStart.current !== null) {
      tracker.recordDwell(impressionId, performance.now() - dwellStart.current);
      dwellStart.current = null;
    }
    if (unregisterCloser.current) {
      unregisterCloser.current();
      unregisterCloser.current = null;
    }
  }, [impressionId]);

  const openDwell = useCallback(() => {
    if (dwellStart.current !== null) return;
    dwellStart.current = performance.now();
    unregisterCloser.current = tracker.registerDwellCloser(() => {
      if (dwellStart.current !== null) {
        tracker.recordDwell(
          impressionId,
          performance.now() - dwellStart.current,
        );
        dwellStart.current = performance.now(); // keep measuring if page returns
      }
    });
  }, [impressionId]);

  useEffect(() => {
    tracker.start();
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        const visibleEnough =
          entry.isIntersecting && entry.intersectionRatio >= 0.5;

        if (visibleEnough && !inView.current) {
          inView.current = true;
          visibleTimer.current = setTimeout(() => {
            tracker.track(impressionId, "visible");
          }, 1_000);
          // Card re-entered while abstract still expanded → resume dwell.
          if (expandedRef.current) openDwell();
        } else if (!visibleEnough && inView.current) {
          inView.current = false;
          if (visibleTimer.current) {
            clearTimeout(visibleTimer.current);
            visibleTimer.current = null;
          }
          // Card left the viewport → finalize any open dwell measurement.
          closeDwell();
        }
      },
      { threshold: [0.5] },
    );
    observer.observe(el);

    return () => {
      observer.disconnect();
      if (visibleTimer.current) clearTimeout(visibleTimer.current);
      closeDwell();
    };
  }, [impressionId, closeDwell, openDwell]);

  /** Call when the abstract is expanded or collapsed. */
  const onExpandChange = useCallback(
    (expanded: boolean) => {
      expandedRef.current = expanded;
      if (expanded) {
        tracker.track(impressionId, "click_abstract"); // deduped after 1st
        openDwell();
      } else {
        closeDwell();
      }
    },
    [impressionId, closeDwell, openDwell],
  );

  return { ref, onExpandChange };
}
