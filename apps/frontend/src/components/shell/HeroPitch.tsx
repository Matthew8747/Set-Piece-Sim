// A hand-drawn tactical diagram for the landing hero: the attacking third with
// an inswinging corner curling toward the near post, attacker runs, marking
// defenders and a keeper. Pure SVG on the design tokens, no data and no deps, so
// it ships in the static page. Decorative: the accessible label carries the gist.

export function HeroPitch() {
  return (
    <svg
      viewBox="0 0 360 300"
      role="img"
      aria-label="Tactical view of an inswinging corner: the delivery curls toward the near post where attackers make runs against marking defenders and the keeper."
      className="h-auto w-full"
    >
      {/* pitch panel */}
      <rect
        x="6"
        y="6"
        width="348"
        height="288"
        rx="12"
        fill="color-mix(in oklab, var(--color-surface-raised) 55%, transparent)"
        stroke="color-mix(in oklab, var(--color-line) 10%, transparent)"
      />

      {/* mowing stripes, very faint */}
      {[0, 1, 2, 3].map((i) => (
        <rect
          key={i}
          x="6"
          y={6 + i * 72}
          width="348"
          height="36"
          fill="color-mix(in oklab, var(--color-line) 2%, transparent)"
        />
      ))}

      <g
        fill="none"
        stroke="color-mix(in oklab, var(--color-line) 22%, transparent)"
        strokeWidth="1.5"
        strokeLinecap="round"
      >
        {/* goal line + goal */}
        <line x1="6" y1="40" x2="354" y2="40" />
        <rect
          x="156"
          y="30"
          width="48"
          height="10"
          stroke="color-mix(in oklab, var(--color-line) 40%, transparent)"
        />
        {/* six-yard box */}
        <path d="M120 40 V78 H240 V40" />
        {/* penalty area */}
        <path d="M70 40 V170 H290 V40" />
        {/* penalty arc */}
        <path d="M132 170 A60 60 0 0 0 228 170" />
        {/* corner arcs */}
        <path d="M6 50 A10 10 0 0 0 16 40" />
        <path d="M354 50 A10 10 0 0 1 344 40" />
      </g>

      {/* penalty spot */}
      <circle
        cx="180"
        cy="124"
        r="2"
        fill="color-mix(in oklab, var(--color-line) 35%, transparent)"
      />

      {/* delivery: inswinger from the right corner curling to the near post */}
      <path
        d="M346 44 Q250 36 212 86"
        fill="none"
        stroke="var(--color-signal)"
        strokeWidth="2"
        strokeDasharray="5 4"
        strokeLinecap="round"
      />
      {/* ball at the contact point */}
      <circle cx="212" cy="86" r="3.5" fill="var(--color-signal)" />
      <circle
        cx="212"
        cy="86"
        r="8"
        fill="none"
        stroke="var(--color-signal)"
        strokeOpacity="0.45"
      />

      {/* attacker runs (short motion cues) */}
      <g
        stroke="color-mix(in oklab, var(--color-signal) 55%, transparent)"
        strokeWidth="1.5"
        strokeLinecap="round"
      >
        <line x1="232" y1="120" x2="216" y2="96" />
        <line x1="150" y1="120" x2="168" y2="100" />
        <line x1="196" y1="150" x2="190" y2="120" />
      </g>

      {/* defenders: goal-side, outlined */}
      <g
        fill="var(--color-surface)"
        stroke="color-mix(in oklab, var(--color-line) 45%, transparent)"
        strokeWidth="1.5"
      >
        <circle cx="198" cy="80" r="5.5" />
        <circle cx="168" cy="92" r="5.5" />
        <circle cx="232" cy="98" r="5.5" />
        <circle cx="182" cy="112" r="5.5" />
      </g>

      {/* attackers: filled, brand */}
      <g fill="var(--color-signal)">
        <circle cx="216" cy="94" r="5.5" />
        <circle cx="168" cy="100" r="5.5" />
        <circle cx="232" cy="118" r="5.5" />
        <circle cx="190" cy="118" r="5.5" />
      </g>

      {/* keeper on the line */}
      <rect x="174" y="44" width="12" height="9" rx="2" fill="var(--color-warn)" />
    </svg>
  );
}
