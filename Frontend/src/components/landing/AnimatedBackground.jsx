import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function AnimatedBackground() {
  const containerRef = useRef(null);
  const orb1Ref = useRef(null);
  const orb2Ref = useRef(null);
  const dnaPath1Ref = useRef(null);
  const dnaPath2Ref = useRef(null);
  const ecgPathRef = useRef(null);
  const [prefersReduced, setPrefersReduced] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Generate DNA coordinates mathematically (100 nodes down the page)
  const numDnaNodes = 80;
  const amplitude = 30; // Width of helix
  const frequency = 0.06; // Winding tightness
  const spacing = 50; // Vertical space between base pairs
  const xCenter = 50; // Center offset inside the SVG viewport

  const dnaNodes = [];
  for (let i = 0; i < numDnaNodes; i++) {
    const y = i * spacing;
    const angle = i * frequency * Math.PI * 2;
    const x1 = xCenter + amplitude * Math.sin(angle);
    const x2 = xCenter + amplitude * Math.sin(angle + Math.PI);
    dnaNodes.push({ id: i, y, x1, x2, isPair: i % 2 === 0 });
  }

  // Create smooth backbone paths
  const dnaPath1D = "M " + dnaNodes.map(n => `${n.x1} ${n.y}`).join(" L ");
  const dnaPath2D = "M " + dnaNodes.map(n => `${n.x2} ${n.y}`).join(" L ");

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);

    // 1. Check for reduced motion preference
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReduced(mediaQuery.matches);
    
    const handleMotionChange = (e) => {
      setPrefersReduced(e.matches);
    };
    mediaQuery.addEventListener('change', handleMotionChange);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      mediaQuery.removeEventListener('change', handleMotionChange);
    };
  }, []);

  useEffect(() => {
    if (prefersReduced) return;

    // 2. Parallax Orbs (Layer 1)
    const ctx = gsap.context(() => {
      gsap.to(orb1Ref.current, {
        y: -150,
        ease: 'none',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: 'bottom bottom',
          scrub: 1
        }
      });

      gsap.to(orb2Ref.current, {
        y: -250,
        ease: 'none',
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: 'bottom bottom',
          scrub: 1.5
        }
      });

      // 3. DNA Drawing Animation (Layer 2)
      const path1 = dnaPath1Ref.current;
      const path2 = dnaPath2Ref.current;
      if (path1 && path2) {
        const len1 = path1.getTotalLength();
        const len2 = path2.getTotalLength();

        gsap.set([path1, path2], {
          strokeDasharray: len1,
          strokeDashoffset: len1
        });

        gsap.to([path1, path2], {
          strokeDashoffset: 0,
          ease: 'none',
          scrollTrigger: {
            trigger: containerRef.current,
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.5
          }
        });
      }

      // DNA Base Pairs Grow on Scroll
      gsap.fromTo('.dna-bar', 
        { scaleX: 0, transformOrigin: 'center center', opacity: 0 },
        {
          scaleX: 1,
          opacity: 0.15,
          ease: 'power1.out',
          stagger: {
            each: 0.01
          },
          scrollTrigger: {
            trigger: containerRef.current,
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.5
          }
        }
      );

      // 4. ECG Pulse & Scroll Spike Animation (Layer 3)
      if (ecgPathRef.current) {
        // Continuous looping heartbeat stroke offset
        gsap.to(ecgPathRef.current, {
          strokeDashoffset: -200,
          repeat: -1,
          duration: 4,
          ease: 'none'
        });

        // ECG Spike when entering capabilities section
        gsap.to(ecgPathRef.current, {
          scaleY: 2.5,
          transformOrigin: 'center center',
          duration: 0.6,
          yoyo: true,
          repeat: 1,
          ease: 'bounce.out',
          scrollTrigger: {
            trigger: '#capabilities-section',
            start: 'top bottom',
            end: 'top center',
            toggleActions: 'play none none reverse'
          }
        });
      }
    }, containerRef);

    // 5. Page Visibility API to pause animations when tab is hidden
    const handleVisibilityChange = () => {
      if (document.hidden) {
        ScrollTrigger.getAll().forEach(trigger => trigger.disable(false));
      } else {
        ScrollTrigger.getAll().forEach(trigger => trigger.enable(false));
        ScrollTrigger.refresh();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      ctx.revert(); // Automatically cleans up all GSAP scroll triggers & animations
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [prefersReduced]);

  return (
    <div ref={containerRef} className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none z-0">
      {/* LAYER 0: Subtle Medical Grid Lines */}
      <div className="absolute inset-0 medical-grid-lines opacity-[0.4] dark:opacity-[0.25]" />

      {/* LAYER 1: Parallax Glowing Orbs */}
      <div 
        ref={orb1Ref}
        className="absolute top-[15%] left-[5%] w-[450px] h-[450px] rounded-full blur-[140px] pointer-events-none will-change-transform"
        style={{
          backgroundColor: 'var(--theme-secondary)',
          opacity: 0.08,
        }}
      />
      <div 
        ref={orb2Ref}
        className="absolute bottom-[20%] right-[10%] w-[550px] h-[550px] rounded-full blur-[160px] pointer-events-none will-change-transform"
        style={{
          backgroundColor: 'var(--theme-primary)',
          opacity: 0.07,
        }}
      />

      {/* LAYER 1.5: Left-side Neural/Constellation motif */}
      <div className="absolute left-0 top-0 h-[800px] w-[350px] hidden md:block z-0 opacity-40">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 350 800">
          {/* Connecting lines */}
          <path
            d="M 60 150 L 140 240 L 90 380 M 140 240 L 220 160 L 280 320 M 220 160 L 120 40 L 40 100 M 280 320 L 190 460 L 230 600 M 190 460 L 90 380 L 110 560"
            fill="none"
            stroke="var(--theme-primary)"
            strokeWidth="1.2"
            strokeDasharray="4 4"
            className="opacity-20"
          />
          {/* Nodes */}
          <circle cx="60" cy="150" r="4.5" fill="var(--theme-secondary)" className="opacity-30" />
          <circle cx="140" cy="240" r="5.5" fill="var(--theme-primary)" className="opacity-45" />
          <circle cx="90" cy="380" r="4.5" fill="var(--theme-accent)" className="opacity-30" />
          <circle cx="220" cy="160" r="6" fill="var(--theme-primary)" className="opacity-40" />
          <circle cx="280" cy="320" r="4" fill="var(--theme-secondary)" className="opacity-30" />
          <circle cx="120" cy="40" r="5" fill="var(--theme-primary)" className="opacity-25" />
          <circle cx="40" cy="100" r="4" fill="var(--theme-secondary)" className="opacity-20" />
          <circle cx="190" cy="460" r="5" fill="var(--theme-accent)" className="opacity-35" />
          <circle cx="230" cy="600" r="4" fill="var(--theme-primary)" className="opacity-25" />
          <circle cx="110" cy="560" r="4.5" fill="var(--theme-secondary)" className="opacity-30" />
        </svg>
      </div>

      {/* LAYER 2: Math-Generated SVG DNA Helix (Right Edge, desktop only) */}
      {!prefersReduced && (
        <div className="absolute right-0 top-0 h-full w-[120px] hidden md:block z-0 opacity-40">
          <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none" viewBox="0 0 100 4000">
            {/* Base Pairs (Bars) */}
            {dnaNodes.map((n) => n.isPair && (
              <line
                key={`bar-${n.id}`}
                x1={n.x1}
                y1={n.y}
                x2={n.x2}
                y2={n.y}
                stroke="var(--theme-primary)"
                strokeWidth="1.5"
                className="dna-bar will-change-transform"
              />
            ))}
            {/* Backbones */}
            <path
              ref={dnaPath1Ref}
              d={dnaPath1D}
              fill="none"
              stroke="var(--theme-primary)"
              strokeWidth="2.5"
              className="opacity-20"
            />
            <path
              ref={dnaPath2Ref}
              d={dnaPath2D}
              fill="none"
              stroke="var(--theme-secondary)"
              strokeWidth="2.5"
              className="opacity-20"
            />
          </svg>
        </div>
      )}

      {/* LAYER 3: Continuous Horizontal ECG line (Positioned between sections) */}
      <div className="absolute top-[110vh] left-0 w-full h-[150px] z-10 opacity-60">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="ecg-glow-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--theme-secondary)" />
              <stop offset="50%" stopColor="var(--theme-primary)" />
              <stop offset="100%" stopColor="var(--theme-secondary)" />
            </linearGradient>
            <filter id="ecg-neon-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path
            ref={ecgPathRef}
            d="M 0 50 L 150 50 L 170 50 L 180 30 L 190 70 L 200 20 L 210 80 L 220 50 L 380 50 L 400 50 L 410 30 L 420 70 L 430 15 L 440 85 L 450 50 L 680 50 L 700 50 L 710 30 L 720 70 L 730 20 L 740 80 L 750 50 L 850 50 L 870 50 L 880 30 L 890 70 L 900 10 L 910 90 L 920 50 L 1000 50"
            fill="none"
            stroke="url(#ecg-glow-grad)"
            strokeWidth="3.5"
            filter="url(#ecg-neon-glow)"
            strokeDasharray="200 200"
            className="will-change-transform"
          />
        </svg>
      </div>

      {/* Dynamic Cursor Glow (Follows cursor in viewport) */}
      <div 
        className="fixed w-[600px] h-[600px] rounded-full blur-[120px] pointer-events-none transition-all duration-200 ease-out z-0 opacity-[0.12] dark:opacity-[0.08]"
        style={{
          background: `radial-gradient(circle, var(--theme-secondary) 0%, transparent 70%)`,
          left: `${mousePos.x - 300}px`,
          top: `${mousePos.y - 300}px`,
        }}
      />
    </div>
  );
}
