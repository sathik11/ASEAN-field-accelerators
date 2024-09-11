import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// export const dynamic = "force-dynamic";
// export const runtime = "edge";

async function parse({
  log,
  send,
  error,
  close,
  question,
}: {
  log: (msg: string) => void;
  send: (msg: string) => void;
  error: (msg: Error | unknown) => void;
  close: () => void;
  question: string;
}) {
  const url = "http://127.0.0.1:8090/score"; // Updated to local endpoint

  try {
    log("Connecting to " + url);
    log("Parameters: " + JSON.stringify({ question })); // Log the parameters
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ question }),
    });

    log("Response status: " + response.status);

    if (!response.ok) {
      throw new Error("Network response was not ok");
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (reader) {
      const readStream = async () => {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          log("Chunk received: " + chunk); // Log the received chunk

          send(chunk); // Send the raw chunk to the client
        }
      };

      await readStream();
      close();
    }
  } catch (err) {
    error(new Error("Failed to connect to SSE: " + err));
  }
}

/**
 * Implements long running response. Only works with edge runtime.
 * @link https://github.com/vercel/next.js/issues/9965
 */
export async function POST(req: NextRequest) {
  const { question } = await req.json(); // Ensure the question is correctly parsed
  console.log("Received question: " + question); // Log the question

  const encoder = new TextEncoder();
  let closed = false;

  const stream = new ReadableStream({
    start(controller) {
      const send = (msg: string) => {
        if (!closed) {
          controller.enqueue(encoder.encode(msg + "\n\n"));
        }
      };

      const close = () => {
        if (!closed) {
          controller.close();
          closed = true;
        }
      };

      parse({
        log: (msg: string) => {
          console.log(msg); // Only log to the server console
        },
        send,
        error: (err: Error | unknown) => {
          send("data: " + (err instanceof Error ? err.message : String(err)));
          close();
        },
        close,
        question,
      })
        .then(() => {
          console.info("Done");
          close();
        })
        .catch((e) => {
          console.error("Failed", e);
          close();
        });
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "text/event-stream; charset=utf-8",
      Connection: "keep-alive",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      "Content-Encoding": "none",
    },
  });
}
