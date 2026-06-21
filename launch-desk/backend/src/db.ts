import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync, type DatabaseSync as SyncDb, type SQLInputValue } from 'node:sqlite';
import { env } from './config/env.js';

let instance: SyncDb | null = null;

export type DbLike = SyncDb;

export const db = {
  get(): DbLike {
    if (!instance) {
      const dbPath = env.databasePath;
      fs.mkdirSync(path.dirname(dbPath), { recursive: true });
      const created = new DatabaseSync(dbPath);
      created.exec('PRAGMA foreign_keys = ON');
      created.exec('PRAGMA journal_mode = WAL');
      instance = created;
    }
    return instance;
  },
};

export const runQuery = <T>(sql: string, params: SQLInputValue[] = []): T[] => {
  return db.get().prepare(sql).all(...params) as T[];
};

export const getRow = <T>(sql: string, params: SQLInputValue[] = []): T | undefined => {
  return db.get().prepare(sql).get(...params) as T | undefined;
};

export const runCommand = (sql: string, params: SQLInputValue[] = []) => {
  return db.get().prepare(sql).run(...params);
};

export const runTransaction = <T>(callback: (db: DbLike) => T): T => {
  const connection = db.get();
  connection.exec('BEGIN IMMEDIATE');
  try {
    const result = callback(connection);
    connection.exec('COMMIT');
    return result;
  } catch (error) {
    connection.exec('ROLLBACK');
    throw error;
  }
};

export const nowIso = () => new Date().toISOString();
