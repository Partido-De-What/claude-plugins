// The pace of the office loop: when a requestAnimationFrame tick is a frame to draw. Pure, so a test can run it at any refresh rate.
// s = {last, acc, drewAt}; returns the real seconds since the last drawn frame, or 0 when this tick is skipped.
export function pace(s, now, fps) {
  s.acc += now - s.last; s.last = now;
  if (s.acc < 1000 / fps - 2) return 0;                                          // 2 ms slack: a 60 cap on a 60 Hz screen must not drop to 30
  // the time left over goes to the next frame (at most one frame's worth): with acc = 0 a 75-165 Hz screen gave 37-55 frames a second
  const dt = Math.min(0.1, (now - (s.drewAt || now - 1000 / fps)) / 1000); s.drewAt = now;
  s.acc = Math.max(0, Math.min(s.acc - 1000 / fps, 1000 / fps));
  return Math.max(dt, 0.001);
}

// The mouse look's filter: a captured pointer on Windows sometimes sends a jump of the cursor (3 events of 700 px in the same instant, a turn of 1.7 rad each,
// seen in a real log), at the capture and in the middle of a look. A hand is never that far from its last steps. reset() on a capture change: nothing for 100 ms.
export function lookFilter() {
  const hist = []; let skipUntil = 0, lastAt = 0;
  return {
    reset(now, ms = 100) { skipUntil = now + ms; hist.length = 0; },
    ok(dx, dy, now) {                                                          // false for a jump of the cursor, true for a hand
      if (now < skipUntil) return false;
      const m = Math.max(Math.abs(dx), Math.abs(dy));
      if (now - lastAt > 300) hist.length = 0; lastAt = now;                   // after a rest the steps start again
      const ref = hist.length ? Math.max(...hist.slice(-3)) : 50;               // the biggest of the last 3 steps (a median lags behind a flick that is speeding up); with none (after a rest) a real flick may start at up to 400
      if (m > 400 || (m > 150 && m > 8 * Math.max(ref, 5))) return false;      // 400 px is a screen's width in 5 frames; or far more than the last steps
      if (m) { hist.push(m); if (hist.length > 8) hist.shift(); }
      return true;
    },
  };
}
