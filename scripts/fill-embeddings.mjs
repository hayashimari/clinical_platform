import OpenAI from "openai";
import pg from "pg";
import dotenv from "dotenv";

dotenv.config();

const { Client } = pg;

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const client = new Client({
  user: "postgres",
  host: "localhost",
  database: "platform",
  password: "postgres",
  port: 5432,
});

await client.connect();

const res = await client.query(
  "SELECT id, content FROM resource_segments WHERE embedding IS NULL"
);

for (const row of res.rows) {
  const embeddingRes = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: row.content,
  });

  const embedding = embeddingRes.data[0].embedding;

  await client.query(
    "UPDATE resource_segments SET embedding = $1 WHERE id = $2",
    [JSON.stringify(embedding), row.id]
  );

  console.log(`Updated id ${row.id}`);
}

await client.end();