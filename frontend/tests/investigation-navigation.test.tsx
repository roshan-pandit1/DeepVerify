import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InvestigationWorkspace from "../src/components/InvestigationWorkspace";
import type { Investigation } from "../src/lib/investigation-api";

const { api } = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("../src/lib/investigation-api", () => ({ api }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function report(id: string, stage = "complete"): Investigation {
  return { claim_id: id, stage, provider: "offline", memory_text: `Claim ${id}`, created_at: "2026-01-01",
    error: null, assertions: [], searches: [], audit: [], related: [], job: null };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  api.mockReset();
  api.mockImplementation((path: string) => {
    if (path === "/investigations") return Promise.resolve([report("A"), report("B")]);
    if (path === "/learning") return Promise.resolve({ status: "collecting", approved_live_examples: 0 });
    throw new Error(`Unexpected path ${path}`);
  });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

async function open() {
  render(<InvestigationWorkspace />);
  await screen.findByRole("button", { name: /Claim A/ });
}
function click(id: string) { fireEvent.click(screen.getByRole("button", { name: new RegExp(`Claim ${id}`) })); }

describe("investigation navigation", () => {
  it("keeps B when A finishes last even if transport ignores cancellation", async () => {
    const a = deferred<Investigation>(), b = deferred<Investigation>();
    await open();
    api.mockImplementation((path: string) => path.endsWith("/A") ? a.promise : b.promise);
    click("A"); click("B");
    await act(async () => b.resolve(report("B")));
    expect(screen.getByText(/ID: B/)).toBeTruthy();
    await act(async () => a.resolve(report("A")));
    expect(screen.getByText(/ID: B/)).toBeTruthy();
    expect(screen.queryByText(/ID: A/)).toBeNull();
    expect(window.location.search).toBe("?investigation=B");
  });

  it("new investigation invalidates pending responses and stale errors", async () => {
    const a = deferred<Investigation>();
    await open(); api.mockReturnValue(a.promise);
    click("A");
    fireEvent.click(screen.getByRole("button", { name: "New investigation" }));
    await act(async () => a.reject(new Error("obsolete failure")));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByLabelText("Investigation report")).toBeNull();
    expect(window.location.search).toBe("");
  });

  it("normal navigation surfaces errors and permits a later selection", async () => {
    await open();
    api.mockRejectedValueOnce(new Error("current failure")); click("A");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "current failure");
    api.mockResolvedValueOnce(report("B")); click("B");
    await screen.findByText(/ID: B/);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("ignores stale polling and aborts it on selection change", async () => {
    await open();
    vi.useFakeTimers();
    api.mockResolvedValueOnce(report("A", "queued"));
    await act(async () => click("A"));
    expect(screen.getByText(/ID: A/)).toBeTruthy();
    const poll = deferred<Investigation>();
    api.mockReturnValueOnce(poll.promise);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    const pollSignal = api.mock.calls.at(-1)?.[4] as AbortSignal;
    api.mockResolvedValueOnce(report("B")); click("B");
    await act(async () => {});
    expect(pollSignal.aborted).toBe(true);
    await act(async () => poll.resolve(report("A")));
    expect(screen.getByText(/ID: B/)).toBeTruthy();
  });

  it("polls to completion and refreshes history without overlapping requests", async () => {
    await open();
    vi.useFakeTimers();
    api.mockResolvedValueOnce(report("A", "queued"));
    await act(async () => click("A"));
    expect(screen.getByText(/ID: A/)).toBeTruthy();
    const poll = deferred<Investigation>(); api.mockReturnValueOnce(poll.promise);
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(api.mock.calls.filter(([p]) => p === "/investigations/A")).toHaveLength(2);
    await act(async () => poll.resolve(report("A")));
    expect(screen.getByText("complete")).toBeTruthy();
    expect(api.mock.calls.filter(([p]) => p === "/investigations").length).toBe(2);
  });

  it("aborts pending load on unmount", async () => {
    await open();
    const a = deferred<Investigation>(); api.mockReturnValueOnce(a.promise); click("A");
    const signal = api.mock.calls.at(-1)?.[4] as AbortSignal;
    cleanup(); expect(signal.aborted).toBe(true);
    await act(async () => a.resolve(report("A")));
    await waitFor(() => expect(screen.queryByLabelText("Investigation report")).toBeNull());
  });
});
