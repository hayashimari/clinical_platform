import pg from "pg";
import OpenAI from "openai";
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

const documents = [
  {
    title: "Heart Failure Management",
    resource_type: "guideline",
    abstract: "Summary of heart failure diagnosis and treatment.",
    source_url: "https://example.com/heart-failure",
    content: `
Heart failure management includes assessment of symptoms, ejection fraction, volume status, and comorbidities.
Treatment may include diuretics for congestion, guideline-directed medical therapy, and monitoring of renal function.
Patients should be evaluated for worsening dyspnea, edema, fatigue, and exercise intolerance.
    `,
  },
  {
    title: "Pneumonia Treatment Overview",
    resource_type: "review",
    abstract: "Overview of pneumonia evaluation and antimicrobial treatment.",
    source_url: "https://example.com/pneumonia",
    content: `
Pneumonia treatment depends on disease severity, suspected pathogens, comorbidities, and local resistance patterns.
Patients should be assessed for fever, cough, sputum production, hypoxia, and radiographic infiltrates.
Antibiotic selection should consider community-acquired or hospital-acquired pneumonia.
    `,
  },
];

function chunkText(text, maxLength = 300) {
  const sentences = text
    .replace(/\s+/g, " ")
    .trim()
    .split(". ")
    .filter(Boolean);

  const chunks = [];
  let current = "";

  for (const sentence of sentences) {
    const next = current ? `${current}. ${sentence}` : sentence;

    if (next.length > maxLength) {
      chunks.push(current);
      current = sentence;
    } else {
      current = next;
    }
  }

  if (current) chunks.push(current);

  return chunks;
}

await client.connect();

for (const doc of documents) {
  const resourceRes = await client.query(
    `
    INSERT INTO resources (title, resource_type, abstract, source_url)
    VALUES ($1, $2, $3, $4)
    RETURNING id
    `,
    [doc.title, doc.resource_type, doc.abstract, doc.source_url]
  );

  const resourceId = resourceRes.rows[0].id;
  const chunks = chunkText(doc.content);

  for (let i = 0; i < chunks.length; i++) {
    const embeddingRes = await openai.embeddings.create({
      model: "text-embedding-3-small",
      input: chunks[i],
    });

    const embedding = embeddingRes.data[0].embedding;

    await client.query(
      `
      INSERT INTO resource_segments (resource_id, segment_index, content, embedding)
      VALUES ($1, $2, $3, $4)
      `,
      [resourceId, i, chunks[i], JSON.stringify(embedding)]
    );

    console.log(`Inserted: ${doc.title} chunk ${i}`);
  }
}

await client.end();

console.log("Done.");