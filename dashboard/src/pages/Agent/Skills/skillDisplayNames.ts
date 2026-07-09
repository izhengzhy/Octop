/**
 * Localised labels for built-in agent skills shown in the dashboard.
 * Labels are defined in backend ``src/octop/i18n/*.json`` (``skills.*``).
 */

import { useTranslation } from "react-i18next";

export interface SkillLabelInput {
  slug?: string;
  name?: string;
}

export function resolveSkillDisplayName(
  skill: SkillLabelInput,
  translate: (slug: string) => string,
): string {
  const slug = skill.slug ?? skill.name ?? "";
  if (!slug) return "";
  const localized = translate(slug);
  if (localized !== slug) return localized;
  return skill.name || slug;
}

export function useSkillDisplayName(): (skill: SkillLabelInput) => string {
  const { t } = useTranslation();

  const translate = (slug: string) => {
    const key = `skills.${slug}`;
    const translated = t(key);
    return translated === key ? slug : translated;
  };

  return (skill: SkillLabelInput) => resolveSkillDisplayName(skill, translate);
}

/** Resolve by slug alone (e.g. expert template preview before agent exists). */
export function useSkillSlugDisplayName(): (slug: string) => string {
  const skillDisplayName = useSkillDisplayName();
  return (slug: string) => skillDisplayName({ slug });
}
