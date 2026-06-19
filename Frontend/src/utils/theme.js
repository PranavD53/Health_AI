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

export const applyTheme = (themeName) => {
  const root = document.documentElement;
  
  // Clear any inline styles set by custom theme
  root.style.removeProperty('--color-primary');
  root.style.removeProperty('--color-secondary');
  root.style.removeProperty('--color-background');
  root.style.removeProperty('--color-surface');
  root.style.removeProperty('--color-primary-container');
  root.style.removeProperty('--color-secondary-container');
  root.style.removeProperty('--color-outline-variant');
  root.style.removeProperty('--color-on-surface');
  root.style.removeProperty('--color-on-surface-variant');
  root.style.removeProperty('--color-surface-container-lowest');
  root.style.removeProperty('--color-surface-container-low');
  root.style.removeProperty('--color-surface-container');
  root.style.removeProperty('--color-surface-container-high');
  root.style.removeProperty('--color-surface-container-highest');
  root.style.removeProperty('--color-outline');

  root.style.removeProperty('--theme-primary');
  root.style.removeProperty('--theme-secondary');
  root.style.removeProperty('--theme-background');
  root.style.removeProperty('--theme-accent');

  root.classList.remove('theme-light', 'theme-dark', 'theme-teal', 'theme-purple', 'theme-rose', 'dark');
  
  let colors = THEME_PRESETS[themeName];

  if (themeName === 'custom') {
    try {
      const customColors = JSON.parse(localStorage.getItem('custom_theme_colors'));
      if (customColors) {
        colors = {
          primary: customColors.primary,
          secondary: customColors.secondary,
          background: customColors.background,
          accent: customColors.accent || '#f43f5e'
        };
      }
    } catch (e) {
      console.error("Failed to parse custom colors in applyTheme:", e);
    }
  }

  if (!colors) {
    colors = THEME_PRESETS.light;
  }

  // Set Task 2 custom properties
  root.style.setProperty('--theme-primary', colors.primary);
  root.style.setProperty('--theme-secondary', colors.secondary);
  root.style.setProperty('--theme-background', colors.background);
  root.style.setProperty('--theme-accent', colors.accent);

  // Apply Tailwind variables
  if (themeName === 'custom') {
    root.style.setProperty('--color-primary', colors.primary);
    root.style.setProperty('--color-secondary', colors.secondary);
    root.style.setProperty('--color-background', colors.background);
    root.style.setProperty('--color-surface', colors.background === '#ffffff' || colors.background === '#f8fafc' ? '#ffffff' : `${colors.background}cc`);
    
    root.style.setProperty('--color-primary-container', `${colors.primary}15`);
    root.style.setProperty('--color-secondary-container', `${colors.secondary}20`);
    root.style.setProperty('--color-outline-variant', `${colors.primary}20`);
    
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

    const textContrast = getContrastColor(colors.background);
    const textSecondary = getContrastSecondary(colors.background);
    
    root.style.setProperty('--color-on-surface', textContrast);
    root.style.setProperty('--color-on-surface-variant', textSecondary);
    
    const isBackgroundDark = getContrastColor(colors.background) === '#f8fafc';
    if (isBackgroundDark) {
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
  } else {
    // Add preset classes
    if (themeName === 'dark') {
      root.classList.add('theme-dark', 'dark');
    } else {
      root.classList.add(`theme-${themeName}`);
    }
  }
};
