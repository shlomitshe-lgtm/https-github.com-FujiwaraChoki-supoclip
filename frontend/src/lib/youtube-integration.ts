import { formatSupportMessage, parseApiError } from "@/lib/api-error";

export interface YouTubeStatus {
  configured: boolean;
  connected: boolean;
  connected_account_id?: string | null;
  connected_at?: string | null;
}

export interface YouTubePublishResult {
  video_id: string | null;
  url: string | null;
  privacy_status: string;
}

export async function fetchYouTubeStatus(): Promise<YouTubeStatus> {
  const response = await fetch("/api/integrations/youtube", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(formatSupportMessage(await parseApiError(response, "Could not load YouTube status.")));
  }
  return response.json();
}

/** Sends the browser to Composio's hosted Google sign-in; it returns to `returnTo`. */
export async function startYouTubeConnect(returnTo: string): Promise<void> {
  const response = await fetch("/api/integrations/youtube/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_url: new URL(returnTo, window.location.origin).toString() }),
  });
  if (!response.ok) {
    throw new Error(formatSupportMessage(await parseApiError(response, "Could not start YouTube connection.")));
  }
  const data = (await response.json()) as { redirect_url: string };
  window.location.href = data.redirect_url;
}

export async function disconnectYouTube(): Promise<void> {
  const response = await fetch("/api/integrations/youtube", { method: "DELETE" });
  if (!response.ok) {
    throw new Error(formatSupportMessage(await parseApiError(response, "Could not disconnect YouTube.")));
  }
}

export async function publishClipToYouTube(
  taskId: string,
  clipId: string,
  body: { title: string; description: string; tags: string; privacy_status: string },
): Promise<YouTubePublishResult> {
  const response = await fetch(`/api/tasks/${taskId}/clips/${clipId}/publish/youtube`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(formatSupportMessage(await parseApiError(response, "YouTube upload failed.")));
  }
  return response.json();
}
