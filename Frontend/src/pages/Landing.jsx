import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import AnimatedBackground from '../components/landing/AnimatedBackground';
import HeroSection from '../components/landing/HeroSection';
import SlidingTextSection from '../components/landing/SlidingTextSection';
import CapabilitiesSection from '../components/landing/CapabilitiesSection';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export default function Landing() {
  const navigate = useNavigate();
  const { theme, setTheme, customColors, setCustomColor, recentPalettes, applyPaletteFromHistory } = useTheme();
  const [showPaletteMenu, setShowPaletteMenu] = useState(false);

  // Initialize Lenis Smooth Scroll & Sync with GSAP ScrollTrigger
  useEffect(() => {
    // Respect system preference for reduced motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // Smooth exponential ease-out
      smoothWheel: true,
      wheelMultiplier: 1.0,
      touchMultiplier: 1.5,
      infinite: false,
    });

    // Update ScrollTrigger on Lenis scroll events
    lenis.on('scroll', ScrollTrigger.update);

    // Sync Lenis frame loops with GSAP ticker
    const gsapTickerCallback = (time) => {
      lenis.raf(time * 1000);
    };
    gsap.ticker.add(gsapTickerCallback);

    // Initial ScrollTrigger refresh after scroll container mounting
    ScrollTrigger.refresh();

    return () => {
      lenis.destroy();
      gsap.ticker.remove(gsapTickerCallback);
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[var(--theme-background)] text-on-surface select-none transition-colors duration-500">
      
      {/* Dynamic Layered Parallax Background */}
      <AnimatedBackground />

      {/* Glassmorphic Navbar */}
      <nav className="fixed top-0 left-0 w-full z-50 px-8 py-4">
        <div className="backdrop-blur-md bg-white/10 dark:bg-black/10 border border-white/20 rounded-2xl px-6 py-3 flex items-center justify-between max-w-7xl mx-auto shadow-sm">
          <div className="flex items-center gap-4">
            <span className="text-2xl font-bold text-[var(--theme-primary)] tracking-tight cursor-pointer" onClick={() => navigate('/')}>HealthAI</span>
            
            {/* Theme Palette Dropdown Selector */}
            <div className="relative">
              <button
                onClick={() => setShowPaletteMenu(!showPaletteMenu)}
                className="p-2 text-on-surface-variant hover:text-[var(--theme-primary)] transition-all duration-300 focus:outline-none rounded-full hover:bg-white/10 dark:hover:bg-white/5 active:scale-95 flex items-center justify-center"
                title="Change Color Palette"
              >
                <span className="material-symbols-outlined text-[22px] select-none">
                  palette
                </span>
              </button>
              {showPaletteMenu && (
                <div className="absolute left-0 mt-2 w-64 bg-white dark:bg-[#111024] border border-outline-variant/30 rounded-2xl shadow-xl p-4 z-50 animate-in fade-in duration-200">
                  <p className="text-[10px] text-outline font-bold uppercase tracking-wider mb-2">Select Theme</p>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    <button
                      type="button"
                      onClick={() => { setTheme('light'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'light' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-[#5c60f5] border border-white"></span>
                      Classic
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTheme('dark'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'dark' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-[#818cf8] border border-white"></span>
                      Midnight
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTheme('teal'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'teal' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-[#0d9488] border border-white"></span>
                      Teal
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTheme('purple'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'purple' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-[#8b5cf6] border border-white"></span>
                      Purple
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTheme('rose'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'rose' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-[#f43f5e] border border-white"></span>
                      Rose
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTheme('custom'); setShowPaletteMenu(false); }}
                      className={`flex items-center gap-2 p-2 rounded-lg text-xs font-semibold hover:bg-surface-container-low dark:hover:bg-white/5 text-left w-full ${theme === 'custom' ? 'text-[var(--theme-primary)] bg-[var(--theme-primary)]/10' : 'text-on-surface dark:text-white'}`}
                    >
                      <span className="w-3.5 h-3.5 rounded-full bg-gradient-to-tr from-pink-500 to-violet-500 border border-white animate-pulse"></span>
                      Custom
                    </button>
                  </div>

                  {theme === 'custom' && (
                    <div className="border-t border-outline-variant/30 pt-3 mt-2 space-y-3">
                      <p className="text-[10px] text-outline font-bold uppercase tracking-wider">Custom Palette</p>
                      
                      {/* Palette Strip Preview */}
                      <div className="flex h-8 w-full rounded-lg overflow-hidden border border-outline-variant/30">
                        <div className="flex-1 h-full" style={{ backgroundColor: customColors.primary }} title="Primary" />
                        <div className="flex-1 h-full" style={{ backgroundColor: customColors.secondary }} title="Secondary" />
                        <div className="flex-1 h-full" style={{ backgroundColor: customColors.background }} title="Background" />
                        <div className="flex-1 h-full" style={{ backgroundColor: customColors.accent }} title="Accent" />
                      </div>

                      {/* Labeled Swatches */}
                      <div className="grid grid-cols-2 gap-2">
                        <div className="flex items-center justify-between border border-outline-variant/20 p-1.5 rounded-lg bg-surface-container-low dark:bg-white/5">
                          <span className="text-[10px] font-medium text-on-surface-variant dark:text-white/70">Primary</span>
                          <div className="relative w-6 h-6 rounded border border-outline-variant/50 overflow-hidden">
                            <input
                              type="color"
                              value={customColors.primary}
                              onChange={(e) => setCustomColor('primary', e.target.value)}
                              className="absolute inset-0 w-10 h-10 -translate-x-2 -translate-y-2 cursor-pointer p-0 border-0"
                            />
                          </div>
                        </div>
                        <div className="flex items-center justify-between border border-outline-variant/20 p-1.5 rounded-lg bg-surface-container-low dark:bg-white/5">
                          <span className="text-[10px] font-medium text-on-surface-variant dark:text-white/70">Secondary</span>
                          <div className="relative w-6 h-6 rounded border border-outline-variant/50 overflow-hidden">
                            <input
                              type="color"
                              value={customColors.secondary}
                              onChange={(e) => setCustomColor('secondary', e.target.value)}
                              className="absolute inset-0 w-10 h-10 -translate-x-2 -translate-y-2 cursor-pointer p-0 border-0"
                            />
                          </div>
                        </div>
                        <div className="flex items-center justify-between border border-outline-variant/20 p-1.5 rounded-lg bg-surface-container-low dark:bg-white/5">
                          <span className="text-[10px] font-medium text-on-surface-variant dark:text-white/70">BG</span>
                          <div className="relative w-6 h-6 rounded border border-outline-variant/50 overflow-hidden">
                            <input
                              type="color"
                              value={customColors.background}
                              onChange={(e) => setCustomColor('background', e.target.value)}
                              className="absolute inset-0 w-10 h-10 -translate-x-2 -translate-y-2 cursor-pointer p-0 border-0"
                            />
                          </div>
                        </div>
                        <div className="flex items-center justify-between border border-outline-variant/20 p-1.5 rounded-lg bg-surface-container-low dark:bg-white/5">
                          <span className="text-[10px] font-medium text-on-surface-variant dark:text-white/70">Accent</span>
                          <div className="relative w-6 h-6 rounded border border-outline-variant/50 overflow-hidden">
                            <input
                              type="color"
                              value={customColors.accent}
                              onChange={(e) => setCustomColor('accent', e.target.value)}
                              className="absolute inset-0 w-10 h-10 -translate-x-2 -translate-y-2 cursor-pointer p-0 border-0"
                            />
                          </div>
                        </div>
                      </div>

                      {/* History Row */}
                      {recentPalettes && recentPalettes.length > 0 && (
                        <div className="border-t border-outline-variant/20 pt-2 mt-2">
                          <p className="text-[9px] text-outline font-bold uppercase tracking-wider mb-1.5">Recent Palettes</p>
                          <div className="space-y-1">
                            {recentPalettes.slice(0, 5).map((palette, index) => (
                              <button
                                type="button"
                                key={palette.id || index}
                                onClick={() => applyPaletteFromHistory(palette)}
                                className="flex h-6 w-full rounded overflow-hidden border border-outline-variant/20 hover:scale-[1.02] transition-transform duration-200"
                              >
                                <div className="flex-1 h-full" style={{ backgroundColor: palette.primary }} />
                                <div className="flex-1 h-full" style={{ backgroundColor: palette.secondary }} />
                                <div className="flex-1 h-full" style={{ backgroundColor: palette.background }} />
                                <div className="flex-1 h-full" style={{ backgroundColor: palette.accent }} />
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/login')}
              className="px-6 py-2 text-on-surface dark:text-white font-semibold hover:text-[var(--theme-primary)] transition-colors focus:outline-none"
            >
              Login
            </button>
            <button
              onClick={() => navigate('/register')}
              className="px-6 py-2 bg-[var(--theme-primary)] hover:opacity-90 text-white rounded-xl font-semibold transition-all shadow-md active:scale-95 focus:outline-none"
            >
              Register
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Pinned Intro */}
      <HeroSection />

      {/* Pinned Text Reveal (Built for doctors...) */}
      <SlidingTextSection />

      {/* Pinned Card Reveal Section */}
      <CapabilitiesSection />

      {/* Security & Compliance Section */}
      <div className="relative z-10 w-full bg-[var(--theme-background)] py-20 border-t border-outline-variant/30 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full blur-[100px] pointer-events-none z-0 bg-[var(--theme-primary)]/5" />
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            
            {/* Left text */}
            <div className="lg:col-span-5 space-y-6 text-center lg:text-left">
              <span className="text-[var(--theme-primary)] font-bold text-xs uppercase tracking-widest block">Security</span>
              <h2 className="font-jakarta text-3xl md:text-4xl font-extrabold text-on-surface leading-tight tracking-tight">
                Enterprise-grade Clinical Security
              </h2>
              <p className="font-inter text-sm md:text-base text-on-surface-variant leading-relaxed">
                HealthAI is built from the ground up on modern cryptographic database frameworks, prioritizing user privacy, strict access logs, and complete compliance.
              </p>
              <div className="flex flex-wrap justify-center lg:justify-start gap-3 pt-2">
                <span className="px-3 py-1.5 rounded-full bg-surface-container-high border border-outline-variant/20 text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">HIPAA Compliant</span>
                <span className="px-3 py-1.5 rounded-full bg-surface-container-high border border-outline-variant/20 text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">SOC2 Audited</span>
                <span className="px-3 py-1.5 rounded-full bg-surface-container-high border border-outline-variant/20 text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">GDPR Safeguarded</span>
              </div>
            </div>

            {/* Right grid */}
            <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-6 shadow-sm hover:border-[var(--theme-primary)]/30 transition-all">
                <span className="material-symbols-outlined text-[var(--theme-primary)] text-2xl mb-4">lock</span>
                <h4 className="font-jakarta text-sm font-bold text-on-surface mb-2">End-to-End Encryption</h4>
                <p className="font-inter text-xs text-on-surface-variant leading-relaxed">
                  All communications and uploaded records are encrypted in transit and at rest using AES-256 standards.
                </p>
              </div>

              <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-6 shadow-sm hover:border-[var(--theme-primary)]/30 transition-all">
                <span className="material-symbols-outlined text-[var(--theme-primary)] text-2xl mb-4">gavel</span>
                <h4 className="font-jakarta text-sm font-bold text-on-surface mb-2">Access Control</h4>
                <p className="font-inter text-xs text-on-surface-variant leading-relaxed">
                  Granular role-based security settings ensure only authorized doctors and patients can access medical files.
                </p>
              </div>

              <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-6 shadow-sm hover:border-[var(--theme-primary)]/30 transition-all">
                <span className="material-symbols-outlined text-[var(--theme-primary)] text-2xl mb-4">clinical_notes</span>
                <h4 className="font-jakarta text-sm font-bold text-on-surface mb-2">Audit Trails</h4>
                <p className="font-inter text-xs text-on-surface-variant leading-relaxed">
                  Every document access, consultation link, and diagnostic query is recorded in immutable compliance logs.
                </p>
              </div>

              <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-6 shadow-sm hover:border-[var(--theme-primary)]/30 transition-all">
                <span className="material-symbols-outlined text-[var(--theme-primary)] text-2xl mb-4">verified_user</span>
                <h4 className="font-jakarta text-sm font-bold text-on-surface mb-2">Secure API Routing</h4>
                <p className="font-inter text-xs text-on-surface-variant leading-relaxed">
                  All external communication routes are authenticated using OAuth2 and signed cryptographic JSON web tokens.
                </p>
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Testimonials Section */}
      <div className="relative z-10 w-full bg-[var(--theme-background)] py-20 border-t border-outline-variant/30">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
            <span className="text-[var(--theme-primary)] font-bold text-xs uppercase tracking-widest block">Testimonials</span>
            <h2 className="font-jakarta text-3xl md:text-4xl font-extrabold text-on-surface tracking-tight">Trusted by Doctors & Patients</h2>
            <p className="font-inter text-sm text-on-surface-variant">Hear from qualified clinical specialists and active patients using HealthAI.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            
            {/* Testimonial 1 */}
            <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-8 shadow-sm relative">
              <span className="material-symbols-outlined text-4xl text-[var(--theme-primary)]/20 absolute top-4 right-6 select-none">format_quote</span>
              <p className="font-inter text-sm text-on-surface-variant leading-relaxed italic mb-6">
                "HealthAI has transformed the way I connect with my patients. The automated AI report analysis saves hours of manual diagnostic reading, allowing me to focus on high-impact treatments during virtual calls."
              </p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[var(--theme-primary)] to-[var(--theme-secondary)] flex items-center justify-center text-white font-bold text-xs">
                  AV
                </div>
                <div>
                  <h4 className="font-jakarta text-sm font-bold text-on-surface">Dr. Alisha Vance, MD</h4>
                  <p className="text-[10px] text-on-surface-variant font-medium">Chief of Cardiology, Vanguard Health</p>
                </div>
              </div>
            </div>

            {/* Testimonial 2 */}
            <div className="bg-white dark:bg-[#0c0c17] border border-outline-variant/50 rounded-2xl p-8 shadow-sm relative">
              <span className="material-symbols-outlined text-4xl text-[var(--theme-primary)]/20 absolute top-4 right-6 select-none">format_quote</span>
              <p className="font-inter text-sm text-on-surface-variant leading-relaxed italic mb-6">
                "The AI symptom checker is absolutely incredible. It gave my family clear triage advice when my son had a high fever at midnight, helping us understand whether to wait or head to the emergency room."
              </p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[var(--theme-secondary)] to-[var(--theme-accent)] flex items-center justify-center text-white font-bold text-xs">
                  SJ
                </div>
                <div>
                  <h4 className="font-jakarta text-sm font-bold text-on-surface">Sarah Jenkins</h4>
                  <p className="text-[10px] text-on-surface-variant font-medium">Verified Platform User since 2024</p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="relative z-10 w-full bg-surface-container-low border-t border-outline-variant/30 pt-16 pb-8">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 pb-12 border-b border-outline-variant/20">
            
            {/* Brand logo & Newsletter */}
            <div className="lg:col-span-2 space-y-4">
              <h3 className="text-xl font-bold text-[var(--theme-primary)]">HealthAI</h3>
              <p className="font-inter text-xs text-on-surface-variant leading-relaxed max-w-sm">
                Next-generation diagnostic checkers, clinical consultation portals, and secure patient timeline indexing.
              </p>
              <div className="pt-2">
                <p className="text-[10px] font-bold text-on-surface uppercase tracking-wider mb-2">Subscribe to newsletter</p>
                <div className="flex max-w-xs gap-2">
                  <input 
                    type="email" 
                    placeholder="Enter email address" 
                    className="flex-1 py-1.5 px-3 border border-outline-variant rounded-lg bg-white dark:bg-[#0c0c17] text-xs text-on-surface focus:outline-none focus:border-[var(--theme-primary)]" 
                  />
                  <button className="px-3.5 py-1.5 bg-[var(--theme-primary)] text-white font-bold text-xs rounded-lg hover:opacity-90 active:scale-95 transition-all">
                    Join
                  </button>
                </div>
              </div>
            </div>

            {/* Sitemap Column 1 */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-bold text-on-surface uppercase tracking-wider">Features</h4>
              <ul className="space-y-2 text-xs font-semibold text-on-surface-variant">
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Symptom Checker</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Doctor Booking</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Vitals Timeline</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Lab Summarizer</span></li>
              </ul>
            </div>

            {/* Sitemap Column 2 */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-bold text-on-surface uppercase tracking-wider">Compliance</h4>
              <ul className="space-y-2 text-xs font-semibold text-on-surface-variant">
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">HIPAA Standards</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">SOC2 Audits</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Encryption Key Management</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Audit Records</span></li>
              </ul>
            </div>

            {/* Sitemap Column 3 */}
            <div className="space-y-3">
              <h4 className="text-[10px] font-bold text-on-surface uppercase tracking-wider">Support</h4>
              <ul className="space-y-2 text-xs font-semibold text-on-surface-variant">
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Knowledge Base</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Clinic Directory</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">Contact Support</span></li>
                <li><span className="hover:text-[var(--theme-primary)] cursor-pointer">File Complaint</span></li>
              </ul>
            </div>

          </div>

          {/* Legal disclaimer and copyrights */}
          <div className="pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-[10px] text-on-surface-variant/80 font-medium max-w-2xl text-center md:text-left leading-normal">
              Disclaimer: HealthAI symptom checker provides diagnostic triaging advice for informational purposes only. It does not replace the professional clinical judgment, physical examination, or treatment recommendation of a certified medical practitioner.
            </p>
            <p className="text-[10px] text-on-surface-variant/75 font-semibold whitespace-nowrap">
              &copy; 2026 HealthAI Inc. All rights reserved.
            </p>
          </div>
        </div>
      </footer>

    </div>
  );
}
