import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function HeroSection() {
  const navigate = useNavigate();
  const containerRef = useRef(null);
  const pinWrapperRef = useRef(null);
  const headlineRef = useRef(null);
  const subtextRef = useRef(null);
  const ctaRef = useRef(null);
  const mockupRef = useRef(null);
  const [isMobile, setIsMobile] = useState(false);
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const checkViewport = () => {
      setIsMobile(window.innerWidth < 1024);
    };
    checkViewport();
    window.addEventListener('resize', checkViewport);

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReduced(mediaQuery.matches);

    return () => {
      window.removeEventListener('resize', checkViewport);
    };
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      if (prefersReduced) {
        gsap.set([headlineRef.current, subtextRef.current, ctaRef.current, mockupRef.current], {
          opacity: 1,
          y: 0,
          scale: 1
        });
        return;
      }

      // Simple, beautiful entrance animation on mount for all viewports
      const tl = gsap.timeline();
      tl.fromTo(headlineRef.current, 
        { opacity: 0, y: 30 }, 
        { opacity: 1, y: 0, duration: 0.8, ease: 'power2.out' }
      )
      .fromTo(subtextRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out' },
        '-=0.4'
      )
      .fromTo(ctaRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' },
        '-=0.3'
      )
      .fromTo(mockupRef.current,
        { opacity: 0, y: 40, scale: 0.96 },
        { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: 'power2.out' },
        '-=0.3'
      );
    }, containerRef);

    return () => {
      ctx.revert();
    };
  }, [prefersReduced]);

  return (
    <div ref={containerRef} className="relative z-10 w-full">
      <div className="w-full min-h-screen flex flex-col justify-center items-center px-6 pt-28 pb-16 lg:py-0">
        <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          
          {/* Left Column: Typography */}
          <div className="lg:col-span-5 text-center lg:text-left flex flex-col items-center lg:items-start space-y-6">
            
            {/* Trust badge */}
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[var(--theme-primary)]/10 border border-[var(--theme-primary)]/20 text-xs font-semibold text-[var(--theme-primary)] tracking-wide animate-pulse">
              <span className="material-symbols-outlined text-[14px]">verified</span>
              Next-Gen Medical Intelligence
            </div>

            {/* Headline */}
            <h1 ref={headlineRef} className="font-jakarta text-4xl sm:text-5xl md:text-[54px] font-extrabold text-on-surface leading-[1.12] tracking-tight">
              Healthcare <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[var(--theme-primary)] to-[var(--theme-secondary)]">
                Reimagined with AI
              </span>
            </h1>

            {/* Subtext */}
            <p ref={subtextRef} className="font-inter text-base md:text-lg text-on-surface-variant leading-relaxed max-w-xl">
              Connect with practitioners, analyze diagnostics reports, check symptoms instantly, and manage your medical records through an intelligent, HIPAA-compliant patient dashboard.
            </p>

            {/* CTAs */}
            <div ref={ctaRef} className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto pt-2">
              <button
                onClick={() => navigate('/register')}
                className="px-8 py-3.5 bg-[var(--theme-primary)] hover:opacity-90 text-white rounded-2xl font-bold shadow-lg transition-all active:scale-[0.98] focus:outline-none w-full sm:w-auto text-center"
              >
                Get Started Free
              </button>
              <button
                onClick={() => {
                  const el = document.getElementById('capabilities-section');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="px-8 py-3.5 bg-surface-container-high border border-outline/35 hover:bg-surface-container-highest text-on-surface rounded-2xl font-semibold transition-all active:scale-[0.98] focus:outline-none w-full sm:w-auto text-center"
              >
                Explore Features
              </button>
            </div>
          </div>

          {/* Right Column: High Fidelity Dashboard Mockup */}
          <div ref={mockupRef} className="lg:col-span-7 w-full flex justify-center">
            <div className="dashboard-mockup-container w-full max-w-2xl bg-white dark:bg-[#0c0c17] border border-outline-variant/60 rounded-3xl p-6 shadow-2xl relative transition-all duration-300 hover:border-[var(--theme-primary)]/40 hover:shadow-primary/5">
              
              {/* Subtle glows in background of mockup */}
              <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-[var(--theme-primary)]/10 blur-2xl pointer-events-none" />
              <div className="absolute -bottom-12 -left-12 w-48 h-48 rounded-full bg-[var(--theme-secondary)]/10 blur-2xl pointer-events-none" />

              {/* Mockup Header bar */}
              <div className="flex justify-between items-center pb-4 mb-6 border-b border-outline-variant/50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[var(--theme-primary)] to-[var(--theme-secondary)] flex items-center justify-center text-white font-bold text-sm">
                    SJ
                  </div>
                  <div>
                    <h4 className="font-bold text-xs text-on-surface">Sarah Jenkins</h4>
                    <p className="text-[10px] text-on-surface-variant font-medium">Patient ID: #HA-9821</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span className="text-[10px] text-emerald-500 font-bold tracking-wide uppercase">Connected</span>
                </div>
              </div>

              {/* Mockup Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                
                {/* Vitals widget */}
                <div className="bg-surface-container-low border border-outline-variant/40 rounded-2xl p-4 flex flex-col justify-between h-36">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Live Heart Rate</span>
                    <span className="material-symbols-outlined text-rose-500 text-lg">favorite</span>
                  </div>
                  <div className="my-2">
                    <h3 className="text-3xl font-extrabold text-on-surface tracking-tight">72 <span className="text-xs text-on-surface-variant font-semibold">BPM</span></h3>
                  </div>
                  <div className="w-full overflow-hidden">
                    <style>{`
                      @keyframes pulseECG {
                        0% { stroke-dashoffset: 400; }
                        100% { stroke-dashoffset: 0; }
                      }
                    `}</style>
                    <svg className="w-full h-8" viewBox="0 0 200 40">
                      <path
                        d="M0 20 L40 20 L50 20 L54 5 L58 35 L62 20 L75 20 L115 20 L125 20 L129 5 L133 35 L137 20 L145 20 L200 20"
                        fill="none"
                        stroke="var(--theme-primary)"
                        strokeWidth="2.5"
                        strokeDasharray="400"
                        strokeDashoffset="400"
                        className="opacity-90"
                        style={{ animation: 'pulseECG 3s linear infinite' }}
                      />
                    </svg>
                  </div>
                </div>

                {/* Patient Health Score Widget */}
                <div className="bg-surface-container-low border border-outline-variant/40 rounded-2xl p-4 flex flex-col justify-between h-36">
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Health Index</span>
                    <span className="material-symbols-outlined text-[var(--theme-primary)] text-lg">show_chart</span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <h3 className="text-3xl font-extrabold text-on-surface tracking-tight">94%</h3>
                    <span className="text-[10px] text-emerald-500 font-bold flex items-center">
                      <span className="material-symbols-outlined text-[10px] font-bold">arrow_upward</span>+2.1%
                    </span>
                  </div>
                  <div className="text-[10px] text-on-surface-variant font-medium leading-normal mb-1">
                    Vitals stable. Activity levels are optimal. Sleep quality rose 8% this week.
                  </div>
                </div>

                {/* AI report analyser */}
                <div className="md:col-span-2 bg-surface-container-low border border-outline-variant/40 rounded-2xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-[var(--theme-primary)] text-lg">psychology</span>
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">AI Report Dissection</span>
                  </div>
                  <div className="space-y-2">
                    <div className="bg-white dark:bg-black/25 border border-outline-variant/20 rounded-xl p-3">
                      <p className="text-[11px] font-semibold text-on-surface leading-relaxed">
                        <span className="text-[var(--theme-primary)] font-bold">Clinical Analysis:</span> CBC report shows mild iron-deficiency anemia (Hb: 10.8 g/dL). Sleep disruption noted. Recommended iron-rich diet & schedule virtual checkup.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="px-2 py-0.5 rounded-full bg-[var(--theme-primary)]/10 text-[9px] font-bold text-[var(--theme-primary)]">Hb: 10.8 g/dL (Low)</span>
                      <span className="px-2 py-0.5 rounded-full bg-[var(--theme-secondary)]/10 text-[9px] font-bold text-[var(--theme-secondary)]">Ferritin: 12 ng/mL</span>
                      <span className="px-2 py-0.5 rounded-full bg-[var(--theme-accent)]/10 text-[9px] font-bold text-[var(--theme-accent)]">Action Required</span>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
