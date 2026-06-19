import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function SlidingTextSection() {
  const containerRef = useRef(null);
  const pinWrapperRef = useRef(null);
  const line1Ref = useRef(null);
  const line2Ref = useRef(null);
  const line3Ref = useRef(null);
  const [isMobile, setIsMobile] = useState(false);
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const checkViewport = () => {
      setIsMobile(window.innerWidth < 768);
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
        gsap.set([line1Ref.current, line2Ref.current, line3Ref.current], { opacity: 1 });
        return;
      }

      if (isMobile) {
        gsap.fromTo(line1Ref.current, { opacity: 0.15 }, {
          opacity: 1,
          scrollTrigger: {
            trigger: line1Ref.current,
            start: 'top 80%',
            end: 'top 50%',
            scrub: true
          }
        });
        gsap.fromTo(line2Ref.current, { opacity: 0.15 }, {
          opacity: 1,
          scrollTrigger: {
            trigger: line2Ref.current,
            start: 'top 80%',
            end: 'top 50%',
            scrub: true
          }
        });
        gsap.fromTo(line3Ref.current, { opacity: 0.15 }, {
          opacity: 1,
          scrollTrigger: {
            trigger: line3Ref.current,
            start: 'top 80%',
            end: 'top 50%',
            scrub: true
          }
        });
        return;
      }

      // Desktop Apple Sticky Typography Scroll Scrub Timeline
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: '+=150%',
          pin: pinWrapperRef.current,
          scrub: 0.5,
          anticipatePin: 1
        }
      });

      // Line 1: Built for doctors.
      tl.to(line1Ref.current, {
        opacity: 1,
        color: 'var(--theme-primary)',
        duration: 1
      });
      tl.to(line1Ref.current, {
        opacity: 0.25,
        color: 'var(--color-on-surface)',
        duration: 1
      });

      // Line 2: Designed for patients.
      tl.to(line2Ref.current, {
        opacity: 1,
        color: 'var(--theme-secondary)',
        duration: 1
      }, '-=0.3');
      tl.to(line2Ref.current, {
        opacity: 0.25,
        color: 'var(--color-on-surface)',
        duration: 1
      });

      // Line 3: Powered by AI.
      tl.to(line3Ref.current, {
        opacity: 1,
        color: 'var(--theme-accent)',
        textShadow: '0 0 30px rgba(var(--theme-primary), 0.2)',
        duration: 1
      }, '-=0.3');

    }, containerRef);

    return () => {
      ctx.revert();
    };
  }, [isMobile, prefersReduced]);

  return (
    <div ref={containerRef} className={`relative z-10 w-full ${isMobile || prefersReduced ? '' : 'min-h-[250vh]'}`}>
      <div ref={pinWrapperRef} className="w-full min-h-screen flex items-center justify-center bg-surface-container-low px-6 py-20 border-y border-outline-variant/30">
        <div className="max-w-4xl mx-auto flex flex-col justify-center space-y-8 md:space-y-12 select-none">
          
          <h2 ref={line1Ref} className="font-jakarta text-4xl sm:text-5xl md:text-7xl font-extrabold leading-tight text-on-surface opacity-[0.15] transition-all duration-300">
            Built for doctors.
          </h2>
          
          <h2 ref={line2Ref} className="font-jakarta text-4xl sm:text-5xl md:text-7xl font-extrabold leading-tight text-on-surface opacity-[0.15] transition-all duration-300">
            Designed for patients.
          </h2>
          
          <h2 ref={line3Ref} className="font-jakarta text-4xl sm:text-5xl md:text-7xl font-extrabold leading-tight text-on-surface opacity-[0.15] transition-all duration-300">
            Powered by AI.
          </h2>
          
        </div>
      </div>
    </div>
  );
}
