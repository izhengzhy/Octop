import type { SkillSpec } from "../../Agent/Skills/useSkills";

export function skillChipLabel(skill: SkillSpec): string {
  if (skill.emoji) return skill.emoji;
  const name = skill.name || skill.slug;
  return name.charAt(0).toUpperCase();
}
