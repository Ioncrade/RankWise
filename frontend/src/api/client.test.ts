import { afterEach, describe, expect, it, vi } from "vitest";

import { RankWiseApi } from "@/api/client";
import type { Job } from "@/api/types";

const succeededJob: Job = {
  job_id: "job_1",
  tenant_id: "class-a",
  kind: "note_generation",
  status: "succeeded",
  payload: {},
  result: { note_id: "note_1" },
  error: null,
  created_at: "2026-09-13T00:00:00+00:00",
  updated_at: "2026-09-13T00:00:01+00:00",
};

afterEach(() => vi.unstubAllGlobals());

describe("RankWiseApi", () => {
  it("scopes collection requests with the configured tenant", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ collections: [], count: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a", "https://api.example").listCollections();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example/v1/collections");
    expect(new Headers(init.headers).get("X-Tenant-ID")).toBe("class-a");
  });

  it("routes study artifacts through the artifact contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(succeededJob), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a").createNote("col_1", {
      title: "Reaction review",
      profile: "reaction_sheet",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/v1/collections/col_1/artifacts");
    expect(JSON.parse(String(init.body))).toMatchObject({
      title: "Reaction review",
      type: "reaction_sheet",
    });
  });

  it("sends the selected generation provider with questions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Local answer [E1]",
          citations: [],
          retrieved_evidence: [],
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a").queryCollection(
      "col_1",
      "What is force?",
      "ollama",
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      query: "What is force?",
      generation_provider: "ollama",
    });
  });

  it("loads provider readiness with tenant scope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ default: "auto", providers: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a").providers();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("X-Tenant-ID")).toBe("class-a");
  });

  it("keeps ordinary notes on the note endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(succeededJob), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a").createNote("col_1", {
      title: "Exam notes",
      profile: "comprehensive",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/v1/collections/col_1/notes");
  });

  it("surfaces the backend typed error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            error: {
              code: "missing_tenant",
              message: "X-Tenant-ID is required",
              details: {},
            },
          }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const request = new RankWiseApi("class-a").listCollections();
    await expect(request).rejects.toMatchObject({
      status: 400,
      code: "missing_tenant",
      message: "X-Tenant-ID is required",
    });
  });

  it("fetches protected evidence images with the tenant header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(["png"]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new RankWiseApi("class-a").renderEvidence({
      render_url: "/v1/evidence/ev_1/render?document_version_id=dv_1",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("X-Tenant-ID")).toBe("class-a");
  });
});
