import fs from 'node:fs';
import path from 'node:path';
import { runCommand, db, getRow, runQuery } from '../src/db';
import { nowIso } from '../src/db';

const migrationsDir = path.resolve(process.cwd(), 'migrations');

const runMigrations = () => {
  const dbi = db.get();
  dbi.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)`);
  const applied = new Set<string>(runQuery<{ version: string }>(`SELECT version FROM schema_migrations`).map((r) => r.version));

  if (!fs.existsSync(migrationsDir)) {
    throw new Error(`Migrations directory missing: ${migrationsDir}`);
  }
  const files = fs.readdirSync(migrationsDir).filter((name) => name.endsWith('.sql')).sort();
  for (const file of files) {
    if (applied.has(file)) {
      continue;
    }
    const sql = fs.readFileSync(path.join(migrationsDir, file), 'utf8');
    dbi.exec('BEGIN IMMEDIATE');
    try {
      dbi.exec(sql);
      runCommand(`INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)`, [file, nowIso()]);
      dbi.exec('COMMIT');
      console.log(`Applied migration: ${file}`);
    } catch (error) {
      dbi.exec('ROLLBACK');
      throw new Error(`Migration failed ${file}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
};

runMigrations();

const hasClinic = getRow<{ id: number }>(`SELECT id FROM clinics ORDER BY id LIMIT 1`);
console.log(`Schema ready. Existing clinic rows: ${hasClinic ? 1 : 0}`);
