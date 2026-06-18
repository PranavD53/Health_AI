---
name: Clinical Intelligence System
colors:
  surface: '#f9f9ff'
  surface-dim: '#cfdaf1'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d8e3fa'
  on-surface: '#111c2c'
  on-surface-variant: '#42474f'
  inverse-surface: '#263142'
  inverse-on-surface: '#ebf1ff'
  outline: '#727780'
  outline-variant: '#c2c7d1'
  surface-tint: '#2d6197'
  primary: '#00355f'
  on-primary: '#ffffff'
  primary-container: '#0f4c81'
  on-primary-container: '#8ebdf9'
  inverse-primary: '#a0c9ff'
  secondary: '#006970'
  on-secondary: '#ffffff'
  secondary-container: '#8df2fc'
  on-secondary-container: '#006f77'
  tertiary: '#303436'
  on-tertiary: '#ffffff'
  tertiary-container: '#474b4d'
  on-tertiary-container: '#b7bbbd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d2e4ff'
  primary-fixed-dim: '#a0c9ff'
  on-primary-fixed: '#001c37'
  on-primary-fixed-variant: '#07497d'
  secondary-fixed: '#8df2fc'
  secondary-fixed-dim: '#70d6df'
  on-secondary-fixed: '#002022'
  on-secondary-fixed-variant: '#004f54'
  tertiary-fixed: '#e0e3e5'
  tertiary-fixed-dim: '#c4c7c9'
  on-tertiary-fixed: '#181c1e'
  on-tertiary-fixed-variant: '#434749'
  background: '#f9f9ff'
  on-background: '#111c2c'
  surface-variant: '#d8e3fa'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style

This design system is built on a foundation of **Corporate Modern** aesthetics blended with **Minimalism** to suit a high-stakes healthcare environment. The brand personality is rooted in "Empathetic Precision"—it must feel as reliable as a medical instrument but as approachable as a trusted caregiver.

The visual language prioritizes clarity, utilizing heavy whitespace to reduce cognitive load for patients and practitioners. Surfaces are kept clean and expansive to evoke a sense of professional hygiene and organization. Every element is designed to foster a sense of calm and competence, ensuring that AI-driven insights are perceived as supportive rather than intrusive.

## Colors

The palette is anchored by **Trust Blue**, a deep, authoritative shade that establishes immediate credibility. **Healing Teal** serves as the primary action and innovation color, bridging the gap between traditional medicine and modern technology.

- **Primary (Trust Blue):** Used for headers, primary brand moments, and structural navigation.
- **Secondary (Healing Teal):** Used for primary buttons, active states, and health-related highlights.
- **Surface (Tertiary):** A very soft blue-gray used for page backgrounds and section containers to prevent the "stark white" eye strain in clinical settings.
- **Accent (Warm Orange):** Reserved strictly for urgent alerts, critical notifications, and "Action Required" states.
- **Neutrals:** A scale of cool grays used for typography and borders to maintain a professional, high-contrast environment.

## Typography

The design system utilizes **Inter** for all roles to ensure maximum legibility across digital interfaces. Inter’s tall x-height and clear letterforms are essential for reading medical data and chat transcripts accurately.

- **Headlines:** Use a tighter letter-spacing and heavier weights to establish a clear hierarchy.
- **Body Text:** Optimized for long-form reading in medical reports and AI chat responses with generous line heights.
- **Labels:** Used for data visualization legends, form field headers, and status badges. Small labels use increased letter spacing and semi-bold weights to remain legible at small scales.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a base unit of **4px**. This allows for precise alignment of dense medical data while maintaining the "spacious" feel requested.

- **Desktop:** 12-column grid with 24px gutters. Max content width is 1440px.
- **Tablet:** 8-column grid with 24px gutters.
- **Mobile:** 4-column grid with 16px gutters and margins.

Spacing should be used to group related medical information. For example, use `md (16px)` between elements in a card, but `2xl (48px)` between major page sections.

## Elevation & Depth

To maintain a clean, clinical feel, the system uses **Tonal Layers** supplemented by **Ambient Shadows**. This avoids the clutter of heavy borders.

- **Level 0 (Base):** Used for the background (Tertiary Color).
- **Level 1 (Cards/Surface):** White background with a very soft, diffused shadow (0px 2px 10px rgba(15, 76, 129, 0.05)).
- **Level 2 (Dropdowns/Modals):** White background with a more pronounced shadow to indicate focus (0px 10px 25px rgba(15, 76, 129, 0.1)).
- **Interactive Depth:** Buttons use a slight lift on hover and a subtle inset shadow on "active" (pressed) states to provide tactile feedback.

## Shapes

The design system employs **Rounded** geometry to soften the clinical nature of the product. This makes the AI feel more approachable and empathetic.

- **Standard (8px):** Primary for buttons, input fields, and small cards.
- **Large (16px):** Used for main container surfaces and modal windows.
- **Extra Large (24px):** Used for chat bubbles and hero sections.
- **Full (Pill):** Strictly reserved for status tags (e.g., "Stable," "Active") and selection chips.

## Components

### Chat Elements
- **AI Response:** Uses the Secondary (Healing Teal) color at a very low opacity (5-10%) for the bubble background to distinguish it from the user.
- **User Message:** White bubble with Level 1 elevation.
- **Thinking State:** A three-dot pulse animation in Healing Teal.

### Role-Based Headers
- **Patient View:** Features a simplified navigation with a "Help/SOS" button prominent.
- **Clinician View:** High-density navigation with quick-access to patient records and data toggle filters.

### Notifications & Toasts
- **Standard Toast:** Positioned top-right, Level 2 elevation, using a left-accent border color to indicate status (Success = Green, Info = Blue).
- **Urgent Alert:** Persistent banner at the top of the viewport using the Warm Orange accent color.

### Data & Loading
- **Skeleton Loaders:** Use a subtle shimmer effect on a light gray base. Shapes should match the component they are replacing (e.g., 8px rounded rectangles for buttons).
- **Icons:** Use linear, 2pt stroke icons for medical categories (Cardiology, Neurology, etc.) for a modern, technical look.

### Controls
- **Buttons:** Primary buttons use a solid Healing Teal fill with white text. Secondary buttons use an outline of Trust Blue.
- **Inputs:** Clean white backgrounds with a 1px border in a light neutral gray. On focus, the border transitions to Healing Teal with a soft glow.