import React from 'react';

export default function ConstellationBackground() {
  // 20 pre-distributed nodes with fixed percentage coordinates for responsiveness.
  const nodes = [
    { id: 0, x: 12, y: 15, pulseDelay: '0s', floatDelay: '0s' },
    { id: 1, x: 28, y: 22, pulseDelay: '1s', floatDelay: '2s' },
    { id: 2, x: 20, y: 45, pulseDelay: '2s', floatDelay: '1s' },
    { id: 3, x: 38, y: 35, pulseDelay: '0.5s', floatDelay: '3s' },
    { id: 4, x: 48, y: 18, pulseDelay: '1.5s', floatDelay: '0.5s' },
    { id: 5, x: 58, y: 40, pulseDelay: '2.5s', floatDelay: '1.5s' },
    { id: 6, x: 72, y: 20, pulseDelay: '3s', floatDelay: '2.5s' },
    { id: 7, x: 85, y: 38, pulseDelay: '1.2s', floatDelay: '0.8s' },
    { id: 8, x: 65, y: 60, pulseDelay: '0.8s', floatDelay: '3.2s' },
    { id: 9, x: 42, y: 68, pulseDelay: '2.2s', floatDelay: '1.2s' },
    { id: 10, x: 18, y: 72, pulseDelay: '1.8s', floatDelay: '2.2s' },
    { id: 11, x: 88, y: 65, pulseDelay: '0.3s', floatDelay: '1.7s' },
    { id: 12, x: 94, y: 30, pulseDelay: '2.7s', floatDelay: '0.3s' },
    { id: 13, x: 78, y: 78, pulseDelay: '1.4s', floatDelay: '2.8s' },
    { id: 14, x: 30, y: 85, pulseDelay: '0.6s', floatDelay: '1.1s' },
    { id: 15, x: 50, y: 90, pulseDelay: '2.1s', floatDelay: '3.5s' },
    { id: 16, x: 68, y: 88, pulseDelay: '1.7s', floatDelay: '0.6s' },
    { id: 17, x: 84, y: 92, pulseDelay: '2.9s', floatDelay: '1.9s' },
    { id: 18, x: 96, y: 82, pulseDelay: '0.2s', floatDelay: '2.4s' },
    { id: 19, x: 58, y: 80, pulseDelay: '1.1s', floatDelay: '0.9s' }
  ];

  // Links connecting nodes that are close to each other.
  const links = [
    { from: 0, to: 1 },
    { from: 0, to: 2 },
    { from: 1, to: 3 },
    { from: 1, to: 4 },
    { from: 2, to: 3 },
    { from: 2, to: 9 },
    { from: 2, to: 10 },
    { from: 3, to: 4 },
    { from: 3, to: 5 },
    { from: 3, to: 9 },
    { from: 4, to: 5 },
    { from: 4, to: 6 },
    { from: 5, to: 6 },
    { from: 5, to: 7 },
    { from: 5, to: 8 },
    { from: 6, to: 7 },
    { from: 6, to: 12 },
    { from: 7, to: 11 },
    { from: 7, to: 12 },
    { from: 8, to: 9 },
    { from: 8, to: 13 },
    { from: 8, to: 19 },
    { from: 9, to: 10 },
    { from: 9, to: 14 },
    { from: 10, to: 14 },
    { from: 11, to: 12 },
    { from: 11, to: 13 },
    { from: 11, to: 17 },
    { from: 11, to: 18 },
    { from: 13, to: 16 },
    { from: 13, to: 17 },
    { from: 14, to: 15 },
    { from: 15, to: 16 },
    { from: 15, to: 19 },
    { from: 16, to: 17 },
    { from: 16, to: 19 },
    { from: 17, to: 18 }
  ];

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none z-0">
      <style>{`
        @keyframes floatNode {
          0%, 100% { transform: translate(0, 0); }
          33% { transform: translate(4px, -6px); }
          66% { transform: translate(-5px, 4px); }
        }
        @keyframes pulseNode {
          0%, 100% { opacity: 0.08; r: 3px; }
          50% { opacity: 0.16; r: 5px; }
        }
        @keyframes pulseLine {
          0%, 100% { opacity: 0.05; stroke-width: 0.5px; }
          50% { opacity: 0.12; stroke-width: 1px; }
        }
        .const-node {
          animation: floatNode 12s ease-in-out infinite alternate;
        }
        .const-node-dot {
          animation: pulseNode 4s ease-in-out infinite;
        }
        .const-line {
          animation: floatNode 12s ease-in-out infinite alternate, pulseLine 6s ease-in-out infinite;
        }
      `}</style>
      <svg className="w-full h-full opacity-80" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--theme-primary)" stopOpacity="0.4" />
            <stop offset="100%" stopColor="var(--theme-primary)" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Lines */}
        {links.map((link, idx) => {
          const fromNode = nodes.find(n => n.id === link.from);
          const toNode = nodes.find(n => n.id === link.to);
          if (!fromNode || !toNode) return null;

          return (
            <line
              key={`line-${idx}`}
              x1={`${fromNode.x}%`}
              y1={`${fromNode.y}%`}
              x2={`${toNode.x}%`}
              y2={`${toNode.y}%`}
              stroke="var(--theme-primary)"
              className="const-line"
              style={{
                animationDelay: fromNode.floatDelay,
                transformOrigin: `${fromNode.x}% ${fromNode.y}%`
              }}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map(node => (
          <g
            key={`node-${node.id}`}
            className="const-node"
            style={{
              animationDelay: node.floatDelay,
              transformOrigin: `${node.x}% ${node.y}%`
            }}
          >
            {/* Glow circle */}
            <circle
              cx={`${node.x}%`}
              cy={`${node.y}%`}
              r="12"
              fill="url(#nodeGlow)"
              opacity="0.15"
            />
            {/* Core dot */}
            <circle
              cx={`${node.x}%`}
              cy={`${node.y}%`}
              fill="var(--theme-secondary)"
              stroke="var(--theme-primary)"
              strokeWidth="1"
              className="const-node-dot"
              style={{ animationDelay: node.pulseDelay }}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
