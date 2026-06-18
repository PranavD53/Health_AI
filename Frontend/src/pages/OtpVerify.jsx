import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function OtpVerify() {
  const navigate = useNavigate();
  const location = useLocation();
  const { checkAuth } = useAuth();
  
  const [email, setEmail] = useState('');
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  
  const inputRefs = useRef([]);

  useEffect(() => {
    if (location.state && location.state.email) {
      setEmail(location.state.email);
    } else {
      // Fallback: ask for email
      const promptEmail = prompt("Please enter the email address you registered with:");
      if (promptEmail) {
        setEmail(promptEmail);
      } else {
        navigate('/login');
      }
    }
  }, [location, navigate]);

  const handleChange = (index, value) => {
    if (isNaN(value)) return;
    
    const newDigits = [...otpDigits];
    newDigits[index] = value;
    setOtpDigits(newDigits);
    
    // Auto focus next input
    if (value !== '' && index < 5) {
      inputRefs.current[index + 1].focus();
    }
  };

  const handleKeyDown = (index, e) => {
    // Handle backspace delete back focus
    if (e.key === 'Backspace' && otpDigits[index] === '' && index > 0) {
      inputRefs.current[index - 1].focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasteData = e.clipboardData.getData('text').trim();
    if (pasteData.length === 6 && !isNaN(pasteData)) {
      const chars = pasteData.split('');
      setOtpDigits(chars);
      inputRefs.current[5].focus();
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    const code = otpDigits.join('');
    if (code.length < 6) {
      setError("Please enter all 6 digits");
      return;
    }

    setLoading(true);
    try {
      await api.verifyOtp(email, code);
      setSuccess(true);
      
      // Update state in AuthContext
      await checkAuth();

      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      console.error(err);
      setError(err.message || "Invalid OTP code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError('');
    try {
      await api.resendOtp(email);
      alert("A verification code has been resent to your email address.");
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to resend verification code.");
    }
  };

  return (
    <div className="bg-background text-on-surface min-h-screen flex items-center justify-center p-margin-mobile">
      <div className="w-full max-w-md bg-white border border-outline-variant rounded-2xl shadow-2xl overflow-hidden glass-panel p-2xl text-center">
        <header className="mb-xl">
          <div className="w-16 h-16 bg-primary-fixed text-primary rounded-full flex items-center justify-center mx-auto mb-lg">
            <span className="material-symbols-outlined text-[36px]">mail</span>
          </div>
          <h3 className="text-on-surface font-headline-lg text-headline-lg mb-xs">Email Verification</h3>
          <p className="text-on-surface-variant font-body-md text-body-md">
            We sent a verification code to <br />
            <strong className="text-secondary">{email}</strong>
          </p>
        </header>

        {error && (
          <div className="p-4 bg-error-container text-on-error-container rounded-xl mb-xl flex items-center justify-center gap-sm">
            <span className="material-symbols-outlined">error</span>
            <p className="text-sm font-semibold">{error}</p>
          </div>
        )}

        {success && (
          <div className="p-4 bg-success/10 text-success rounded-xl mb-xl flex items-center justify-center gap-sm">
            <span className="material-symbols-outlined">check_circle</span>
            <p className="text-sm font-bold">Verification Successful! Access Granted.</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-xl">
          <div className="flex justify-between gap-xs md:gap-sm" onPaste={handlePaste}>
            {otpDigits.map((digit, idx) => (
              <input
                key={idx}
                ref={(el) => (inputRefs.current[idx] = el)}
                type="text"
                maxLength="1"
                value={digit}
                onChange={(e) => handleChange(idx, e.target.value)}
                onKeyDown={(e) => handleKeyDown(idx, e)}
                className="w-12 h-14 text-center text-xl font-bold rounded-xl border border-outline-variant bg-surface focus:border-secondary focus:ring-1 focus:ring-secondary outline-none transition-all"
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || success}
            className="w-full py-3.5 bg-primary hover:bg-primary/95 text-white font-bold rounded-lg transition-colors flex items-center justify-center gap-xs focus:outline-none shadow-md"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>
                <span className="material-symbols-outlined">verified</span>
                Verify Code
              </>
            )}
          </button>
        </form>

        <footer className="mt-xl text-center">
          <p className="text-body-md text-on-surface-variant">
            Did not receive the email? <br />
            <button 
              onClick={handleResendOtp}
              className="text-secondary font-bold hover:underline mt-sm"
            >
              Resend OTP Code
            </button>
          </p>
        </footer>
      </div>
    </div>
  );
}
