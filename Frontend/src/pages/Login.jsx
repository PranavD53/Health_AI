import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function Login() {
  const { login, checkAuth } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Input Refs for focusing
  const emailInputRef = useRef(null);
  const passwordInputRef = useRef(null);
  const forgotEmailInputRef = useRef(null);
  const forgotOtpInputRef = useRef(null);

  // Forgot Password States
  const [showForgot, setShowForgot] = useState(false);
  const [forgotOtpSent, setForgotOtpSent] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotOtp, setForgotOtp] = useState('');
  const [forgotError, setForgotError] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);

  const handleRequestForgotOtp = async (e) => {
    e.preventDefault();
    setForgotError('');
    setForgotSuccess('');
    setForgotLoading(true);
    try {
      await api.forgotPassword(forgotEmail);
      setForgotOtpSent(true);
      setForgotSuccess("A 6-digit verification code has been dispatched to your email address.");
    } catch (err) {
      console.error(err);
      setForgotError(err.message || "Failed to send verification code. Check email address.");
    } finally {
      setForgotLoading(false);
    }
  };

  const handleVerifyForgotOtp = async (e) => {
    e.preventDefault();
    setForgotError('');
    setForgotLoading(true);
    try {
      await api.forgotPasswordVerify(forgotEmail, forgotOtp);
      await checkAuth();
      navigate('/dashboard');
    } catch (err) {
      console.error(err);
      setForgotError(err.message || "Invalid OTP code. Please retry.");
    } finally {
      setForgotLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await login(email, password);
      // Check if user is verified
      if (!data.is_verified) {
        // Redirect to OTP verification
        navigate('/otp-verify', { state: { email } });
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to login. Please check credentials.");
    } finally {
      setLoading(false);
    }
  };

  const switchTab = () => {}; // No-op, retired role tabs

  return (
    <div className="bg-background text-on-surface min-h-screen flex overflow-hidden">
      {/* Left Branding Section (Desktop Only) */}
      <section className="hidden lg:flex flex-col justify-between w-[45%] bg-primary relative overflow-hidden p-3xl">
        <div className="relative z-10">
          <div className="flex items-center gap-sm mb-xl">
            <span className="material-symbols-outlined text-primary-fixed-dim text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>health_and_safety</span>
            <h1 className="text-white font-headline-lg text-headline-lg tracking-tight">HealthAI</h1>
          </div>
          <div className="max-w-md">
            <h2 className="text-white font-display-lg text-4xl mb-md leading-tight">Precision Intelligence for Human Wellness.</h2>
            <p className="text-primary-fixed font-body-lg text-body-lg opacity-80">Access your clinical dashboard, patient records, and AI-driven diagnostic tools with enterprise-grade security.</p>
          </div>
        </div>
        <div className="relative z-10">
          <div className="flex gap-lg items-center text-primary-fixed-dim opacity-60">
            <div className="flex flex-col">
              <span className="text-label-sm font-label-sm">ISO 27001</span>
              <span className="text-label-sm font-label-sm">HIPAA COMPLIANT</span>
            </div>
            <div className="h-8 w-px bg-white/20"></div>
            <div className="flex flex-col">
              <span className="text-label-sm font-label-sm">ENCRYPTION</span>
              <span className="text-label-sm font-label-sm">AES-256 BIT</span>
            </div>
          </div>
        </div>
        {/* Abstract Medical Background Image */}
        <div className="absolute bottom-0 right-0 w-full h-full -z-10 mix-blend-overlay">
          <div 
            className="w-full h-full bg-cover bg-center" 
            style={{ backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuAneSzkINXhT4E7YNKfuaeuVDeXneIxWoDNJIyi1bvDS4EByUp5lDkaZgbYQBeqgfSApPp9bd13IGFMjlE0KPbWUJv8hRna3Nu_O-GwR3c4jQzi9Da9schzqvXixy7-Xcf3Flb7-UMSUsj9xanTMsh3kIULdy3MfnC8-_3Y-A43HAY81zeq64N5tVg7mQFXR9EWNoaE2qEX38_uT9vuhsenTzn-uSO1oGz9xsl5LHaDV2jHTpplKzsQGt2sW_0PICfkhnXJ1oOIUL0')" }}
          />
        </div>
      </section>

      {/* Right Login Section */}
      <main className="w-full lg:w-[55%] h-screen overflow-y-auto flex flex-col items-center p-margin-mobile md:p-2xl bg-surface-container-lowest animate-in fade-in duration-300">
        <div className="w-full max-w-lg my-auto py-xl">
          {/* Mobile Logo */}
          <div className="flex lg:hidden items-center justify-center gap-sm mb-xl">
            <span className="material-symbols-outlined text-primary text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>health_and_safety</span>
            <span className="text-primary font-headline-lg text-headline-lg tracking-tight">HealthAI</span>
          </div>

          {showForgot ? (
            <div className="space-y-lg animate-in fade-in duration-200">
              <header className="mb-xl text-center lg:text-left">
                <h3 className="text-on-surface font-headline-lg text-headline-lg mb-xs">Reset Access</h3>
                <p className="text-on-surface-variant font-body-md text-body-md">
                  {!forgotOtpSent 
                    ? "Enter your email address to receive a verification OTP." 
                    : "Enter the 6-digit OTP code sent to your email to sign in directly."}
                </p>
              </header>

              {forgotError && (
                <div className="p-4 bg-error-container text-on-error-container rounded-xl flex items-center gap-sm">
                  <span className="material-symbols-outlined">error</span>
                  <p className="text-sm">{forgotError}</p>
                </div>
              )}

              {forgotSuccess && (
                <div className="p-4 bg-success/15 text-success rounded-xl flex items-center gap-sm">
                  <span className="material-symbols-outlined">check_circle</span>
                  <p className="text-sm">{forgotSuccess}</p>
                </div>
              )}

              {!forgotOtpSent ? (
                <form onSubmit={handleRequestForgotOtp} className="space-y-lg">
                  <div className="space-y-xs">
                    <label className="text-label-md font-label-md text-on-surface ml-unit">Email Address</label>
                    <div className="relative cursor-text" onClick={() => forgotEmailInputRef.current?.focus()}>
                      <span className="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-outline select-none">mail</span>
                      <input 
                        ref={forgotEmailInputRef}
                        autoFocus
                        required
                        type="email" 
                        value={forgotEmail}
                        onChange={(e) => setForgotEmail(e.target.value)}
                        className="w-full pl-[48px] pr-md py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-sm"
                        placeholder="name@example.com"
                      />
                    </div>
                  </div>

                  <button 
                    type="submit" 
                    disabled={forgotLoading}
                    className="w-full py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-sm"
                  >
                    {forgotLoading ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <>
                        <span className="material-symbols-outlined">send</span>
                        Send OTP Login Code
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyForgotOtp} className="space-y-lg">
                  <div className="space-y-xs">
                    <label className="text-label-md font-label-md text-on-surface ml-unit">Verification OTP Code</label>
                    <div className="relative cursor-text" onClick={() => forgotOtpInputRef.current?.focus()}>
                      <span className="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-outline select-none">key</span>
                      <input 
                        ref={forgotOtpInputRef}
                        autoFocus
                        required
                        type="text" 
                        maxLength="6"
                        value={forgotOtp}
                        onChange={(e) => setForgotOtp(e.target.value)}
                        className="w-full pl-[48px] pr-md py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary outline-none text-sm font-semibold tracking-[4px] text-center"
                        placeholder="123456"
                      />
                    </div>
                  </div>

                  <button 
                    type="submit" 
                    disabled={forgotLoading}
                    className="w-full py-3 bg-secondary hover:bg-secondary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-sm"
                  >
                    {forgotLoading ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    ) : (
                      <>
                        <span className="material-symbols-outlined">verified_user</span>
                        Verify & Sign In Directly
                      </>
                    )}
                  </button>
                </form>
              )}

              <div className="text-center mt-lg">
                <button 
                  onClick={() => {
                    setShowForgot(false);
                    setForgotOtpSent(false);
                    setForgotEmail('');
                    setForgotOtp('');
                    setForgotError('');
                    setForgotSuccess('');
                  }}
                  className="text-xs font-bold text-outline hover:text-on-surface hover:underline focus:outline-none"
                >
                  Back to Sign In
                </button>
              </div>
            </div>
          ) : (
            <>
              <header className="mb-xl text-center lg:text-left">
                <h3 className="text-on-surface font-headline-lg text-headline-lg mb-xs">Welcome back</h3>
                <p className="text-on-surface-variant font-body-md text-body-md">Enter your credentials to access your clinical workspace.</p>
              </header>

              {error && (
                <div className="p-4 bg-error-container text-on-error-container rounded-xl mb-xl flex items-center gap-sm">
                  <span className="material-symbols-outlined">error</span>
                  <p className="text-sm">{error}</p>
                </div>
              )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-lg">
            <div className="space-y-xs">
              <label className="text-label-md font-label-md text-on-surface ml-unit">Email Address</label>
              <div className="relative cursor-text" onClick={() => emailInputRef.current?.focus()}>
                <span className="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-outline select-none">mail</span>
                <input 
                  ref={emailInputRef}
                  autoFocus
                  required
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-[48px] pr-md py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary focus:ring-1 focus:ring-secondary outline-none transition-all text-sm"
                  placeholder="name@example.com"
                />
              </div>
            </div>

             <div className="space-y-xs">
              <div className="flex justify-between items-center px-unit">
                <label className="text-label-md font-label-md text-on-surface">Password</label>
                <button 
                  type="button"
                  onClick={() => { setShowForgot(true); setError(''); }}
                  className="text-xs font-bold text-primary hover:underline focus:outline-none"
                >
                  Forgot Password?
                </button>
              </div>
              <div className="relative cursor-text" onClick={(e) => {
                if (!e.target.closest('button')) {
                  passwordInputRef.current?.focus();
                }
              }}>
                <span className="material-symbols-outlined absolute left-md top-1/2 -translate-y-1/2 text-outline select-none">lock</span>
                <input 
                  ref={passwordInputRef}
                  required
                  type={showPassword ? "text" : "password"} 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-[48px] pr-[44px] py-3 rounded-lg border border-outline-variant bg-surface focus:border-secondary focus:ring-1 focus:ring-secondary outline-none transition-all text-sm"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-md top-1/2 -translate-y-1/2 text-outline hover:text-on-surface focus:outline-none flex items-center"
                >
                  <span className="material-symbols-outlined text-lg select-none">
                    {showPassword ? "visibility_off" : "visibility"}
                  </span>
                </button>
              </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full py-3 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-sm"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              ) : (
                <>
                  <span className="material-symbols-outlined">login</span>
                  Sign In
                </>
              )}
            </button>
          </form>

          <footer className="mt-xl text-center">
            <p className="text-body-md text-on-surface-variant">
              Don't have an account?{' '}
              <Link to="/register" className="text-secondary font-bold hover:underline">
                Register account
              </Link>
            </p>
          </footer>
        </>
      )}
        </div>
      </main>
    </div>
  );
}
