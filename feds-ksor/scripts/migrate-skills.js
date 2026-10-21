/**
 * Migration script: Move FEDS skills to KSoR Rung 1 format.
 * 
 * Reads skills from ../.claude/skills/ and writes them to ./knowledge/
 * with OKF frontmatter (owner, audience, status, sources, freshness, lifecycle).
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const SKILLS_DIR = path.join(PROJECT_ROOT, '.claude', 'skills');
const KNOWLEDGE_DIR = path.join(__dirname, '..', 'knowledge');

async function readSkill(skillPath) {
  const content = await fs.readFile(skillPath, 'utf-8');
  if (!content.startsWith('---')) return null;
  
  const parts = content.split('---', 3);
  if (parts.length < 3) return null;
  
  const frontmatter = {};
  for (const line of parts[1].split('\n')) {
    const [key, ...rest] = line.split(':');
    if (key && rest.length > 0) {
      frontmatter[key.trim()] = rest.join(':').trim();
    }
  }
  
  const body = parts[2].trim();
  return { frontmatter, body };
}

async function getReferences(skillDir) {
  const refsDir = path.join(skillDir, 'references');
  try {
    const files = await fs.readdir(refsDir);
    const refs = [];
    for (const f of files) {
      if (f.endsWith('.md') || f.endsWith('.txt')) {
        const refPath = path.join('references', f);
        const fullPath = path.join(skillDir, refPath);
        try {
          await fs.access(fullPath);
          refs.push(refPath);
        } catch {
          console.warn(`    ⚠ Missing reference file: ${refPath}`);
        }
      }
    }
    return refs;
  } catch {
    return [];
  }
}

function toOKF(frontmatter, body, references) {
  const now = new Date().toISOString().split('T')[0];
  const skillName = frontmatter.name || path.basename(skillPath, '.md');
  
  return {
    title: frontmatter.name || skillName,
    description: frontmatter.description || '',
    owner: 'feds-team',
    audience: ['public'],
    status: 'draft',
    sources: references,
    freshness: now,
    lifecycle: 'active',
    tags: ['feds', 'skill', 'frontend'],
    version: frontmatter.version || '1.0.0',
  };
}

function writeOKF(frontmatter, body) {
  const fmLines = Object.entries(frontmatter).map(([key, value]) => {
    if (Array.isArray(value)) {
      return `${key}: [${value.map(v => `"${v}"`).join(', ')}]`;
    }
    return `${key}: "${value}"`;
  });
  return `---\n${fmLines.join('\n')}\n---\n\n${body}`;
}

async function main() {
  console.log('Migrating FEDS skills to KSoR Rung 1...');
  
  await fs.mkdir(KNOWLEDGE_DIR, { recursive: true });
  
  const skillDirs = (await fs.readdir(SKILLS_DIR, { withFileTypes: true }))
    .filter(d => d.isDirectory())
    .map(d => d.name);
  
  console.log(`Found ${skillDirs.length} skills to migrate.`);
  
  for (const skillName of skillDirs) {
    const skillPath = path.join(SKILLS_DIR, skillName, 'SKILL.md');
    const skillDir = path.join(SKILLS_DIR, skillName);
    
    try {
      const skill = await readSkill(skillPath);
      if (!skill) {
        console.warn(`  ⚠ ${skillName}: No valid SKILL.md found`);
        continue;
      }
      
      const references = await getReferences(skillDir);
      const okfFrontmatter = toOKF(skill.frontmatter, skill.body, references);
      const output = writeOKF(okfFrontmatter, skill.body);
      
      const outDir = path.join(KNOWLEDGE_DIR, skillName);
      await fs.mkdir(outDir, { recursive: true });
      await fs.writeFile(path.join(outDir, 'index.md'), output, 'utf-8');
      
      // Copy references (skip missing)
      for (const ref of references) {
        const src = path.join(SKILLS_DIR, ref);
        const dst = path.join(outDir, ref);
        try {
          await fs.mkdir(path.dirname(dst), { recursive: true });
          const content = await fs.readFile(src, 'utf-8');
          await fs.writeFile(dst, content, 'utf-8');
        } catch (err) {
          console.warn(`    ⚠ Missing reference file: ${ref}`);
        }
      }
      
      console.log(`  ✓ ${skillName} (${references.length} refs)`);
    } catch (err) {
      console.error(`  ✗ ${skillName}: ${err}`);
    }
  }
  
  // Generate llms.txt
  const allSkills = [];
  for (const skillName of skillDirs) {
    const indexPath = path.join(KNOWLEDGE_DIR, skillName, 'index.md');
    try {
      const content = await fs.readFile(indexPath, 'utf-8');
      const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
      if (fmMatch) {
        const lines = fmMatch[1].split('\n');
        const fm = {};
        for (const line of lines) {
          const [key, ...rest] = line.split(':');
          if (key && rest.length) {
            fm[key.trim()] = rest.join(':').trim().replace(/^"|"$/g, '');
          }
        }
        allSkills.push({
          name: fm.title,
          description: fm.description,
          path: `knowledge/${skillName}/index.md`,
        });
      }
    } catch {}
  }
  
  const llmsTxt = `# FEDS Skills (KSoR Rung 1)\n\n` +
    allSkills.map(s => `- [${s.name}](${s.path}): ${s.description}`).join('\n');
  
  await fs.writeFile(path.join(KNOWLEDGE_DIR, '..', 'llms.txt'), llmsTxt, 'utf-8');
  
  console.log('\nMigration complete!');
  console.log(`Generated: ${KNOWLEDGE_DIR}`);
  console.log(`Generated: llms.txt`);
}

main().catch(console.error);