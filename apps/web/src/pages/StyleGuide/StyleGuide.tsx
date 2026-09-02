import { useEffect, useState } from 'react';

import { Button } from '../../components/Button/Button';
import { Card } from '../../components/Card/Card';
import { Input } from '../../components/Input/Input';
import {
  applyTheme,
  getThemePreference,
  saveThemePreference,
  subscribeToSystemTheme,
  type ThemePreference,
} from '../../theme/theme';
import styles from './StyleGuide.module.scss';

const themes: ThemePreference[] = ['light', 'dark', 'system'];

const colors = [
  { label: 'Background', className: styles.background },
  { label: 'Surface', className: styles.surface },
  { label: 'Hover surface', className: styles.surfaceHover },
  { label: 'Border', className: styles.border },
  { label: 'Primary', className: styles.primary },
  { label: 'Primary subtle', className: styles.primarySubtle },
  { label: 'Destructive', className: styles.danger },
  { label: 'Destructive subtle', className: styles.dangerSubtle },
  { label: 'Success', className: styles.success },
  { label: 'Success subtle', className: styles.successSubtle },
];

const typeSizes = [
  { label: 'XS · 12px', className: styles.typeXs },
  { label: 'SM · 14px', className: styles.typeSm },
  { label: 'MD · 16px', className: styles.typeMd },
  { label: 'LG · 18px', className: styles.typeLg },
  { label: 'XL · 20px', className: styles.typeXl },
  { label: '2XL · 24px', className: styles.type2xl },
  { label: '3XL · 30px', className: styles.type3xl },
];

export function StyleGuide() {
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference);

  useEffect(() => {
    applyTheme(theme);

    if (theme !== 'system') {
      return undefined;
    }

    return subscribeToSystemTheme(() => applyTheme('system'));
  }, [theme]);

  function selectTheme(preference: ThemePreference) {
    saveThemePreference(preference);
    setTheme(preference);
  }

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <div>
          <p className={styles.eyebrow}>Design system · v1</p>
          <h1>Warm, restrained foundations.</h1>
          <p>
            Semantic tokens and a compact set of native components for the
            document intelligence product.
          </p>
        </div>

        <div
          className={styles.themeControl}
          aria-label="Theme preference"
          role="group"
        >
          {themes.map((preference) => (
            <Button
              aria-pressed={theme === preference}
              key={preference}
              onClick={() => selectTheme(preference)}
              variant={theme === preference ? 'primary' : 'ghost'}
            >
              {preference[0].toUpperCase() + preference.slice(1)}
            </Button>
          ))}
        </div>
      </header>

      <section className={styles.section} aria-labelledby="colors-heading">
        <div className={styles.sectionHeading}>
          <p>01</p>
          <div>
            <h2 id="colors-heading">Semantic colors</h2>
            <span>
              Olive neutrals with Amber actions, Red danger, and Green success.
            </span>
          </div>
        </div>
        <div className={styles.swatchGrid}>
          {colors.map((color) => (
            <Card className={styles.swatchCard} key={color.label}>
              <div className={`${styles.swatch} ${color.className}`} />
              <span>{color.label}</span>
            </Card>
          ))}
        </div>
      </section>

      <section className={styles.section} aria-labelledby="typography-heading">
        <div className={styles.sectionHeading}>
          <p>02</p>
          <div>
            <h2 id="typography-heading">Typography</h2>
            <span>Inter, sized for dense and readable product interfaces.</span>
          </div>
        </div>
        <Card className={styles.typeCard}>
          <div className={styles.typeScale}>
            {typeSizes.map((typeSize) => (
              <p className={typeSize.className} key={typeSize.label}>
                <span>{typeSize.label}</span>
                Document intelligence
              </p>
            ))}
          </div>
          <div className={styles.typeDetails}>
            <div>
              <span>Weight</span>
              <p className={styles.regular}>Regular 400</p>
              <p className={styles.medium}>Medium 500</p>
              <p className={styles.semibold}>Semibold 600</p>
              <p className={styles.bold}>Bold 700</p>
            </div>
            <div>
              <span>Hierarchy</span>
              <p className={styles.primaryText}>Primary text</p>
              <p className={styles.secondaryText}>Secondary text</p>
              <p className={styles.mutedText}>Muted text</p>
            </div>
          </div>
        </Card>
      </section>

      <section className={styles.section} aria-labelledby="components-heading">
        <div className={styles.sectionHeading}>
          <p>03</p>
          <div>
            <h2 id="components-heading">Components</h2>
            <span>
              Hover, press, tab-focus, and disabled states are ready to inspect.
            </span>
          </div>
        </div>
        <div className={styles.componentGrid}>
          <Card className={styles.componentCard}>
            <div className={styles.componentTitle}>
              <h3>Button</h3>
              <span>Four intent variants</span>
            </div>
            <div className={styles.buttonRow}>
              <Button>Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">Danger</Button>
            </div>
            <div className={styles.buttonRow} aria-label="Disabled buttons">
              <Button disabled>Primary</Button>
              <Button disabled variant="secondary">
                Secondary
              </Button>
              <Button disabled variant="ghost">
                Ghost
              </Button>
              <Button disabled variant="danger">
                Danger
              </Button>
            </div>
          </Card>

          <Card className={styles.componentCard}>
            <div className={styles.componentTitle}>
              <h3>Input</h3>
              <span>Native field behavior</span>
            </div>
            <label className={styles.field}>
              <span>Document name</span>
              <Input placeholder="e.g. Q4 annual report" />
            </label>
            <label className={styles.field}>
              <span>Disabled input</span>
              <Input disabled placeholder="Processing document…" />
            </label>
          </Card>

          <Card className={`${styles.componentCard} ${styles.cardExample}`}>
            <div className={styles.statusBadge}>Ready</div>
            <div>
              <p className={styles.cardLabel}>Source document</p>
              <h3>Annual report 2025.pdf</h3>
              <p>Parsed into 214 elements with source-aware provenance.</p>
            </div>
            <Button variant="secondary">View document</Button>
          </Card>
        </div>
      </section>
    </div>
  );
}
