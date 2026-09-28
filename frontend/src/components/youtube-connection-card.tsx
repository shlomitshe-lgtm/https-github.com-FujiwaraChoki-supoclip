"use client";

import { useEffect, useState } from "react";
import { Youtube, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  disconnectYouTube,
  fetchYouTubeStatus,
  startYouTubeConnect,
  type YouTubeStatus,
} from "@/lib/youtube-integration";

export function YouTubeConnectionCard() {
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchYouTubeStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load YouTube status."));
  }, []);

  const handleConnect = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await startYouTubeConnect("/settings?youtube=connected");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start YouTube connection.");
      setIsBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await disconnectYouTube();
      setStatus((current) => (current ? { ...current, connected: false } : current));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not disconnect YouTube.");
    } finally {
      setIsBusy(false);
    }
  };

  let description = "Checking connection…";
  if (status && !status.configured) description = "Not available: the server has no COMPOSIO_API_KEY";
  else if (status?.connected) description = "Connected — publish clips as YouTube Shorts";
  else if (status) description = "Connect your channel to publish clips as Shorts";

  return (
    <div className="p-4 border rounded-lg space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Youtube className="w-5 h-5 text-red-600" />
          <div>
            <p className="text-sm font-medium text-black">YouTube</p>
            <p className="text-xs text-gray-500">{description}</p>
          </div>
        </div>
        {status?.configured && (
          status.connected ? (
            <Button size="sm" variant="outline" disabled={isBusy} onClick={handleDisconnect}>
              {isBusy && <Loader2 className="w-4 h-4 animate-spin" />}
              Disconnect
            </Button>
          ) : (
            <Button size="sm" disabled={isBusy} onClick={handleConnect}>
              {isBusy && <Loader2 className="w-4 h-4 animate-spin" />}
              Connect
            </Button>
          )
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
