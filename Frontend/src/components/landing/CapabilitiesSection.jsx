import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useLanguage } from '../../context/LanguageContext';

gsap.registerPlugin(ScrollTrigger);

export default function CapabilitiesSection() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const containerRef = useRef(null);
  const [prefersReduced, setPrefersReduced] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReduced(mediaQuery.matches);
  }, []);

  useEffect(() => {
    const ctx = gsap.context(() => {
      if (prefersReduced) {
        gsap.set('.feature-card', { opacity: 1, y: 0 });
        return;
      }

      gsap.fromTo('.feature-card',
        { opacity: 0, y: 40 },
        {
          opacity: 1,
          y: 0,
          stagger: 0.1,
          duration: 0.8,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: containerRef.current,
            start: 'top 80%',
            toggleActions: 'play none none reverse'
          }
        }
      );
    }, containerRef);

    return () => {
      ctx.revert();
    };
  }, [prefersReduced]);

  const features = [
    {
      icon: 'psychology',
      titleKey: 'featureTriageTitle',
      descKey: 'featureTriageDesc',
      tagKey: 'featureTriage'
    },
    {
      icon: 'video_call',
      titleKey: 'featureTelemedTitle',
      descKey: 'featureTelemedDesc',
      tagKey: 'featureTelemed'
    },
    {
      icon: 'pill',
      titleKey: 'featureRxSafetyTitle',
      descKey: 'featureRxSafetyDesc',
      tagKey: 'featureRxSafety'
    },
    {
      icon: 'analytics',
      titleKey: 'featureDiagTitle',
      descKey: 'featureDiagDesc',
      tagKey: 'featureDiag'
    },
    {
      icon: 'favorite',
      titleKey: 'featureVitalsTitle',
      descKey: 'featureVitalsDesc',
      tagKey: 'featureVitals'
    },
    {
      icon: 'emergency_share',
      titleKey: 'featureEmergencyTitle',
      descKey: 'featureEmergencyDesc',
      tagKey: 'featureEmergency'
    }
  ];

  return (
    <div 
      id="capabilities-section" 
      ref={containerRef} 
      className="relative z-10 w-full bg-[var(--theme-background)] py-24 border-t border-outline-variant/30"
    >
      {/* Subtle background glow */}
      <div className="absolute top-[20%] left-[10%] w-[350px] h-[350px] rounded-full blur-[100px] pointer-events-none z-0 bg-[var(--theme-primary)]/5 dark:bg-[var(--theme-primary)]/5" />
      <div className="absolute bottom-[20%] right-[10%] w-[350px] h-[350px] rounded-full blur-[100px] pointer-events-none z-0 bg-[var(--theme-secondary)]/5 dark:bg-[var(--theme-secondary)]/5" />

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto mb-20 space-y-3">
          <span className="text-[var(--theme-primary)] font-bold text-xs uppercase tracking-widest block">
            {t('landingCapabilities')}
          </span>
          <h2 className="font-jakarta text-3xl md:text-5xl font-extrabold text-on-surface tracking-tight leading-tight">
            {t('landingIntelligentHealth')}
          </h2>
          <p className="font-inter text-sm md:text-base text-on-surface-variant leading-relaxed">
            {t('landingServicesSubtitle')}
          </p>
        </div>

        {/* 3x2 Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feat, idx) => (
            <div 
              key={idx} 
              className="feature-card group bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-6 lg:p-8 flex flex-col justify-between shadow-sm transition-all duration-300 hover:border-[var(--theme-primary)]/40 hover:-translate-y-1 hover:shadow-lg"
            >
              <div>
                {/* Header Row */}
                <div className="flex justify-between items-center mb-6">
                  <div className="w-12 h-12 rounded-xl bg-[var(--theme-primary)]/10 text-[var(--theme-primary)] flex items-center justify-center shadow-inner group-hover:bg-[var(--theme-primary)] group-hover:text-white transition-all duration-350">
                    <span className="material-symbols-outlined text-[22px] select-none">{feat.icon}</span>
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-surface-container-high text-[9px] font-bold text-on-surface-variant uppercase tracking-wider">
                    {t(feat.tagKey)}
                  </span>
                </div>

                {/* Typography */}
                <h3 className="font-jakarta text-lg font-bold text-on-surface mb-3 group-hover:text-[var(--theme-primary)] transition-colors duration-200">
                  {t(feat.titleKey)}
                </h3>
                <p className="font-inter text-xs md:text-sm text-on-surface-variant leading-relaxed mb-6">
                  {t(feat.descKey)}
                </p>
              </div>

              {/* Action Link */}
              <div 
                onClick={() => navigate('/register')}
                className="flex items-center gap-1.5 text-xs font-bold text-[var(--theme-primary)] cursor-pointer group/link hover:opacity-85"
              >
                {t('learnMore')}
                <span className="material-symbols-outlined text-xs transition-transform duration-200 group-hover/link:translate-x-1">
                  arrow_forward
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Statistics & Badges summary */}
        <div className="mt-20 pt-10 border-t border-outline-variant/30 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <h4 className="font-jakarta text-3xl font-extrabold text-on-surface">{t('statCheckerAccuracyVal')}</h4>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider mt-1">{t('statCheckerAccuracyLbl')}</p>
          </div>
          <div>
            <h4 className="font-jakarta text-3xl font-extrabold text-on-surface">{t('statConsultationsVal')}</h4>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider mt-1">{t('statConsultationsLbl')}</p>
          </div>
          <div>
            <h4 className="font-jakarta text-3xl font-extrabold text-on-surface">{t('statResponseVal')}</h4>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider mt-1">{t('statResponseLbl')}</p>
          </div>
          <div>
            <h4 className="font-jakarta text-3xl font-extrabold text-on-surface">{t('statArchitectureVal')}</h4>
            <p className="text-[10px] text-on-surface-variant font-bold uppercase tracking-wider mt-1">{t('statArchitectureLbl')}</p>
          </div>
        </div>

      </div>
    </div>
  );
}
