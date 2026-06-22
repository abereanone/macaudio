// Thin helpers over the D1 binding. Keep queries explicit & parameterised.
export type DB = D1Database;

export function getDB(locals: App.Locals): DB {
  const db = locals.runtime?.env?.DB;
  if (!db) throw new Error("D1 binding 'DB' is not available");
  return db;
}

export async function one<T = Record<string, unknown>>(db: DB, sql: string, ...params: unknown[]): Promise<T | null> {
  return (await db.prepare(sql).bind(...params).first<T>()) as T | null;
}

export async function all<T = Record<string, unknown>>(db: DB, sql: string, ...params: unknown[]): Promise<T[]> {
  const res = await db.prepare(sql).bind(...params).all<T>();
  return res.results ?? [];
}

export async function run(db: DB, sql: string, ...params: unknown[]): Promise<D1Result> {
  return db.prepare(sql).bind(...params).run();
}
