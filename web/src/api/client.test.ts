import { getResource, postResource } from "./client";

describe("API client response validation", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("rejects a resource with null data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ availability: "available", generated_at: null, data: null })
      })
    );

    await expect(getResource("/api/funds")).rejects.toThrow("invalid resource payload");
  });

  it("rejects a non-object write response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ["legacy"]
      })
    );

    await expect(postResource("/api/reviews/r1", { status: "open" })).rejects.toThrow(
      "invalid resource payload"
    );
  });
});
