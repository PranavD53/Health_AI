import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import { useAuth } from './AuthContext';

const ThemeContext = createContext(null);

const DEFAULT_CUSTOM_COLORS = {
  primary: '#6366f1',      // Indigo
  secondary: '#8b5cf6',    // Violet
  background: '#090916',   // Deep Navy
  accent: '#f43f5e'        // Pink/Coral
};

const THEME_PRESETS = {
  light: {
    primary: '#5c60f5',
    secondary: '#ebdffc',
    background: '#f8fafc',
    accent: '#f43f5e'
  },
  dark: {
    primary: '#818cf8',
    secondary: '#311c52',
    background: '#090916',
    accent: '#f43f5e'
  },
  teal: {
    primary: '#0d9488',
    secondary: '#ccfbf1',
    background: '#f0fdfa',
    accent: '#0891b2'
  },
  purple: {
    primary: '#8b5cf6',
    secondary: '#ebdffc',
    background: '#faf5ff',
    accent: '#d946ef'
  },
  rose: {
    primary: '#f43f5e',
    secondary: '#ffedd5',
    background: '#fff5f5',
    accent: '#fb923c'
  }
};

export const ThemeProvider = ({ children }) => {
  const { user } = useAuth();
  
  const [theme, setThemeState] = useState(() => {
    return localStorage.getItem('theme') || 'light';
  });

  const [customColors, setCustomColors] = useState(() => {
    try {
      const local = localStorage.getItem('custom_theme_colors');
      return local ? JSON.parse(local) : DEFAULT_CUSTOM_COLORS;
    } catch {
      return DEFAULT_CUSTOM_COLORS;
    }
  });

  const [recentPalettes, setRecentPalettes] = useState(() => {
    try {
      const local = localStorage.getItem('custom_theme_history');
      return local ? JSON.parse(local) : [];
    } catch {
      return [];
    }
  });

  const saveTimeoutRef = useRef(null);

  // Apply theme to document element
  const applyThemeVariables = (colors, activeTheme) => {
    const root = document.documentElement;

    // Apply exact Task 2 theme variables
    root.style.setProperty('--theme-primary', colors.primary);
    root.style.setProperty('--theme-secondary', colors.secondary);
    root.style.setProperty('--theme-background', colors.background);
    root.style.setProperty('--theme-accent', colors.accent);

    // Sync to existing Tailwind v4 --color-* theme properties for app-wide UI styling
    root.style.setProperty('--color-primary', colors.primary);
    root.style.setProperty('--color-secondary', colors.secondary);
    root.style.setProperty('--color-background', colors.background);
    
    // Also derive primary/secondary container styling for dashboard card gradients
    root.style.setProperty('--color-primary-container', `${colors.primary}15`);
    root.style.setProperty('--color-secondary-container', `${colors.secondary}20`);
    root.style.setProperty('--color-outline-variant', `${colors.primary}20`);

    // Determine contrast / text colors dynamically
    const getContrastColor = (hexcolor) => {
      if (!hexcolor || hexcolor.length < 6) return '#0f172a';
      const hex = hexcolor.replace('#', '');
      const r = parseInt(hex.substring(0, 2), 16);
      const g = parseInt(hex.substring(2, 4), 16);
      const b = parseInt(hex.substring(4, 6), 16);
      const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
      return (yiq >= 128) ? '#0f172a' : '#f8fafc';
    };

    const getContrastSecondary = (hexcolor) => {
      if (!hexcolor || hexcolor.length < 6) return '#475569';
      const hex = hexcolor.replace('#', '');
      const r = parseInt(hex.substring(0, 2), 16);
      const g = parseInt(hex.substring(2, 4), 16);
      const b = parseInt(hex.substring(4, 6), 16);
      const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
      return (yiq >= 128) ? '#475569' : '#94a3b8';
    };

    // Calculate background brightness
    const textContrast = getContrastColor(colors.background);
    const textSecondary = getContrastSecondary(colors.background);
    
    root.style.setProperty('--color-on-surface', textContrast);
    root.style.setProperty('--color-on-surface-variant', textSecondary);
    root.style.setProperty('--color-surface', colors.background === '#ffffff' || colors.background === '#f8fafc' ? '#ffffff' : `${colors.background}cc`);

    // Toggle .dark class based on background color brightness
    const isDark = getContrastColor(colors.background) === '#f8fafc';
    
    root.classList.remove('theme-light', 'theme-dark', 'theme-teal', 'theme-purple', 'theme-rose', 'dark');
    
    if (isDark) {
      root.classList.add('dark');
      root.style.setProperty('--color-surface-container-lowest', '#05050d');
      root.style.setProperty('--color-surface-container-low', '#0d0c1d');
      root.style.setProperty('--color-surface-container', colors.background);
      root.style.setProperty('--color-surface-container-high', '#1e1b38');
      root.style.setProperty('--color-surface-container-highest', '#2d2a4a');
      root.style.setProperty('--color-outline', '#475569');
    } else {
      root.style.setProperty('--color-surface-container-lowest', '#ffffff');
      root.style.setProperty('--color-surface-container-low', '#f1f5f9');
      root.style.setProperty('--color-surface-container', colors.background);
      root.style.setProperty('--color-surface-container-high', '#f1f5f9');
      root.style.setProperty('--color-surface-container-highest', '#e2e8f0');
      root.style.setProperty('--color-outline', '#94a3b8');
    }

    if (activeTheme !== 'custom') {
      root.classList.add(`theme-${activeTheme}`);
    }
  };

  // Fetch palette settings from DB on load or user login
  const loadUserPalettes = async () => {
    if (!user) {
      // Local fallback on mount / logout
      const local = localStorage.getItem('custom_theme_colors');
      if (local) {
        setCustomColors(JSON.parse(local));
      }
      const localHistory = localStorage.getItem('custom_theme_history');
      if (localHistory) {
        setRecentPalettes(JSON.parse(localHistory));
      }
      return;
    }

    try {
      const data = await api.getPalettes();
      
      // If user has an active custom palette, restore it
      if (data.active) {
        const activeCols = {
          primary: data.active.primary_color,
          secondary: data.active.secondary_color,
          background: data.active.background_color,
          accent: data.active.accent_color
        };
        setCustomColors(activeCols);
        localStorage.setItem('custom_theme_colors', JSON.stringify(activeCols));
      }
      
      // Map history items
      if (data.history && data.history.length > 0) {
        const historyCols = data.history.map(item => ({
          id: item.id,
          primary: item.primary_color,
          secondary: item.secondary_color,
          background: item.background_color,
          accent: item.accent_color,
          is_active: item.is_active
        }));
        setRecentPalettes(historyCols);
        localStorage.setItem('custom_theme_history', JSON.stringify(historyCols));
      }
    } catch (err) {
      console.error('Failed to load user color palettes:', err);
    }
  };

  // Migrate local storage theme to database on login
  const migrateLocalTheme = async () => {
    if (!user) return;
    const local = localStorage.getItem('custom_theme_colors');
    if (!local) return;

    try {
      const colors = JSON.parse(local);
      // Only migrate if different from default
      if (JSON.stringify(colors) !== JSON.stringify(DEFAULT_CUSTOM_COLORS)) {
        await api.savePalette(colors);
        // Clear local migration flag so it doesn't run continuously
        localStorage.removeItem('custom_theme_colors');
      }
    } catch (err) {
      console.error('Failed to migrate local theme settings:', err);
    }
  };

  useEffect(() => {
    loadUserPalettes();
  }, [user]);

  // Handle migration on login
  useEffect(() => {
    if (user) {
      migrateLocalTheme().then(() => {
        loadUserPalettes();
      });
    }
  }, [user]);

  // Synchronize CSS variables when theme or custom colors change
  useEffect(() => {
    const activeColors = theme === 'custom' ? customColors : (THEME_PRESETS[theme] || THEME_PRESETS.light);
    applyThemeVariables(activeColors, theme);
    localStorage.setItem('theme', theme);
    // Fire a global event to notify components like navigation of theme change
    window.dispatchEvent(new Event('theme_change'));
  }, [theme, customColors]);

  // Set the theme preset mode (light, dark, teal, purple, rose, custom)
  const setTheme = (newTheme) => {
    setThemeState(newTheme);
  };

  // Live update color picker with debounced database write (500ms)
  const setCustomColor = (role, colorHex) => {
    // 1. Live update custom color state immediately
    const updated = {
      ...customColors,
      [role]: colorHex
    };
    setCustomColors(updated);
    
    // Update local storage instantly
    localStorage.setItem('custom_theme_colors', JSON.stringify(updated));

    // Ensure we are in custom theme mode
    if (theme !== 'custom') {
      setThemeState('custom');
    }

    // 2. Debounce writing to database
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(async () => {
      if (user) {
        try {
          const savedItem = await api.savePalette(updated);
          // Refresh user palettes to pull new history list
          await loadUserPalettes();
        } catch (err) {
          console.error('Failed to persist custom palette to backend:', err);
        }
      } else {
        // Unauthenticated local history update
        setRecentPalettes(prev => {
          const list = [
            { id: Date.now().toString(), ...updated },
            ...prev.filter(x => JSON.stringify({
              primary: x.primary,
              secondary: x.secondary,
              background: x.background,
              accent: x.accent
            }) !== JSON.stringify(updated))
          ].slice(0, 5);
          localStorage.setItem('custom_theme_history', JSON.stringify(list));
          return list;
        });
      }
    }, 500);
  };

  // Re-apply a past theme from history instantly
  const applyPaletteFromHistory = async (palette) => {
    const updated = {
      primary: palette.primary,
      secondary: palette.secondary,
      background: palette.background,
      accent: palette.accent
    };

    setCustomColors(updated);
    setThemeState('custom');
    localStorage.setItem('custom_theme_colors', JSON.stringify(updated));

    if (user && palette.id) {
      try {
        await api.activatePalette(palette.id);
        await loadUserPalettes();
      } catch (err) {
        console.error('Failed to activate palette in DB:', err);
      }
    } else if (!user) {
      // Local shift
      setRecentPalettes(prev => {
        const list = [
          palette,
          ...prev.filter(x => x.id !== palette.id)
        ].slice(0, 5);
        localStorage.setItem('custom_theme_history', JSON.stringify(list));
        return list;
      });
    }
  };

  return (
    <ThemeContext.Provider value={{
      theme,
      setTheme,
      customColors,
      setCustomColor,
      recentPalettes,
      applyPaletteFromHistory
    }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
