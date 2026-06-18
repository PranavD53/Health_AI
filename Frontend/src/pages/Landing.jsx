import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Landing() {
  const navigate = useNavigate();
  const canvasRef = useRef(null);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Canvas animation for interactive sine waves and ripple effects
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationId;
    let time = 0;
    const ripples = [];
    const mouse = { x: 0, y: 0 };

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleClick = (e) => {
      ripples.push({
        x: e.clientX,
        y: e.clientY,
        radius: 0,
        maxRadius: 200,
        alpha: 1,
        speed: 3
      });
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('click', handleClick);

    const drawSineWaves = () => {
      const waves = [
        { amplitude: 50, frequency: 0.01, speed: 0.02, color: 'rgba(92, 96, 245, 0.3)' },
        { amplitude: 40, frequency: 0.015, speed: 0.03, color: 'rgba(129, 140, 248, 0.25)' },
        { amplitude: 30, frequency: 0.02, speed: 0.025, color: 'rgba(109, 40, 217, 0.2)' }
      ];

      waves.forEach(wave => {
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);

        for (let x = 0; x < canvas.width; x++) {
          const y = canvas.height / 2 + 
                   Math.sin(x * wave.frequency + time * wave.speed) * wave.amplitude +
                   Math.sin(x * wave.frequency * 0.5 + time * wave.speed * 0.8) * (wave.amplitude * 0.5);
          ctx.lineTo(x, y);
        }

        ctx.strokeStyle = wave.color;
        ctx.lineWidth = 2;
        ctx.stroke();
      });
    };

    const drawRipples = () => {
      for (let i = ripples.length - 1; i >= 0; i--) {
        const ripple = ripples[i];
        ripple.radius += ripple.speed;
        ripple.alpha -= 0.02;

        if (ripple.alpha <= 0) {
          ripples.splice(i, 1);
          continue;
        }

        ctx.beginPath();
        ctx.arc(ripple.x, ripple.y, ripple.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(92, 96, 245, ${ripple.alpha})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    };

    const drawGlowingOrbs = () => {
      const orbs = [
        { x: canvas.width * 0.2, y: canvas.height * 0.3, radius: 100, color: 'rgba(92, 96, 245, 0.15)' },
        { x: canvas.width * 0.8, y: canvas.height * 0.7, radius: 120, color: 'rgba(129, 140, 248, 0.12)' },
        { x: canvas.width * 0.5, y: canvas.height * 0.5, radius: 80, color: 'rgba(109, 40, 217, 0.1)' }
      ];

      orbs.forEach(orb => {
        const gradient = ctx.createRadialGradient(orb.x, orb.y, 0, orb.x, orb.y, orb.radius);
        gradient.addColorStop(0, orb.color);
        gradient.addColorStop(1, 'transparent');
        
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      });
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Background gradient
      const bgGradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
      if (theme === 'dark') {
        bgGradient.addColorStop(0, '#090916');
        bgGradient.addColorStop(1, '#111024');
      } else {
        bgGradient.addColorStop(0, '#f8fafc');
        bgGradient.addColorStop(1, '#ffffff');
      }
      ctx.fillStyle = bgGradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      drawGlowingOrbs();
      drawSineWaves();
      drawRipples();

      time += 1;
      animationId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('click', handleClick);
      cancelAnimationFrame(animationId);
    };
  }, [theme]);

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Canvas Background */}
      <canvas
        ref={canvasRef}
        className="fixed top-0 left-0 w-full h-full"
        style={{ zIndex: 0 }}
      />

      {/* Glassmorphic Navbar */}
      <nav className="fixed top-0 left-0 w-full z-50 px-8 py-4">
        <div className="glass-panel rounded-2xl px-6 py-3 flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <span className="text-2xl font-bold text-primary tracking-tight">HealthAI</span>
            <button
              onClick={toggleTheme}
              className="p-2 text-on-surface-variant hover:text-primary transition-all duration-300 focus:outline-none rounded-full hover:bg-surface-container-high active:scale-95 flex items-center justify-center"
              title={theme === 'light' ? "Switch to Dark Mode" : "Switch to Light Mode"}
            >
              <span className="material-symbols-outlined text-[22px] transition-transform duration-500 hover:rotate-[30deg]">
                {theme === 'light' ? 'dark_mode' : 'light_mode'}
              </span>
            </button>
          </div>
          
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/login')}
              className="px-6 py-2 text-on-surface font-semibold hover:text-primary transition-colors focus:outline-none"
            >
              Login
            </button>
            <button
              onClick={() => navigate('/register')}
              className="px-6 py-2 bg-primary hover:bg-primary/95 text-on-primary rounded-xl font-semibold transition-all shadow-md active:scale-95 focus:outline-none"
            >
              Register
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="relative z-10 flex flex-col items-center justify-center min-h-screen px-4">
        <div className="text-center max-w-4xl mx-auto">
          <h1 className="text-5xl md:text-7xl font-bold text-on-surface mb-6 animate-in fade-in slide-in-from-bottom-4 duration-1000">
            Your Health, <span className="text-primary">Simplified</span>
          </h1>
          <p className="text-lg md:text-xl text-on-surface-variant mb-12 max-w-2xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-200">
            Discover doctors, manage medical records, and connect with healthcare professionals through our intelligent AI-powered platform.
          </p>
          
          {/* Feature Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12 animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-300">
            <div className="interactive-card glass-panel rounded-2xl p-6 text-center">
              <span className="material-symbols-outlined text-4xl text-secondary mb-4">search</span>
              <h3 className="text-lg font-bold text-on-surface mb-2">Find Doctors</h3>
              <p className="text-sm text-on-surface-variant">Search and book appointments with qualified healthcare professionals</p>
            </div>
            <div className="interactive-card glass-panel rounded-2xl p-6 text-center">
              <span className="material-symbols-outlined text-4xl text-secondary mb-4">folder</span>
              <h3 className="text-lg font-bold text-on-surface mb-2">Medical Records</h3>
              <p className="text-sm text-on-surface-variant">Securely store and access your medical history anytime</p>
            </div>
            <div className="interactive-card glass-panel rounded-2xl p-6 text-center">
              <span className="material-symbols-outlined text-4xl text-secondary mb-4">chat</span>
              <h3 className="text-lg font-bold text-on-surface mb-2">Private Messaging</h3>
              <p className="text-sm text-on-surface-variant">Communicate privately with doctors and healthcare providers</p>
            </div>
          </div>

          {/* Get Started Button */}
          <button
            onClick={() => navigate('/register')}
            className="group relative px-8 py-4 bg-primary hover:bg-primary/95 text-on-primary rounded-2xl font-bold text-lg transition-all shadow-2xl active:scale-95 focus:outline-none animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-400"
          >
            <span className="relative z-10">Get Started</span>
            <div className="absolute inset-0 rounded-2xl bg-primary opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-xl"></div>
            <div className="absolute inset-0 rounded-2xl border-2 border-primary/30 group-hover:border-primary/60 transition-colors duration-300"></div>
          </button>
        </div>
      </div>
    </div>
  );
}
