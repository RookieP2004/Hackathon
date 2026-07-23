'use client';

import { useEffect, useRef, useState } from 'react';
import { animate, useMotionValue, useMotionValueEvent } from 'framer-motion';

interface CountUpProps {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

/**
 * Odometer-style animated digit transition — UI_UX_SPECIFICATION.md §2's
 * Plant Health Score calls for a "count-up" on value change, not an instant
 * jump, so a live tick reads as motion rather than a flicker.
 */
export function CountUp({ value, decimals = 0, suffix = '', className }: CountUpProps) {
  const motionValue = useMotionValue(value);
  const [display, setDisplay] = useState(value);
  const previous = useRef(value);

  useMotionValueEvent(motionValue, 'change', (latest) => setDisplay(latest));

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
    });
    previous.current = value;
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <span className={className}>
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}
