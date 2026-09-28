"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Loader2, Youtube } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchYouTubeStatus,
  publishClipToYouTube,
  startYouTubeConnect,
  type YouTubePublishResult,
  type YouTubeStatus,
} from "@/lib/youtube-integration";

interface YouTubePublishDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  taskId: string;
  clipId: string;
  defaultTitle: string;
  defaultDescription?: string;
}

export function YouTubePublishDialog({
  open,
  onOpenChange,
  taskId,
  clipId,
  defaultTitle,
  defaultDescription = "",
}: YouTubePublishDialogProps) {
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState(defaultDescription);
  const [tags, setTags] = useState("");
  const [privacy, setPrivacy] = useState("private");
  const [isBusy, setIsBusy] = useState(false);
  const [result, setResult] = useState<YouTubePublishResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle(defaultTitle);
    setDescription(defaultDescription);
    setResult(null);
    setError(null);
    setStatus(null);
    fetchYouTubeStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load YouTube status."));
  }, [open, defaultTitle, defaultDescription]);

  const handleConnect = async () => {
    setIsBusy(true);
    try {
      await startYouTubeConnect(window.location.pathname + window.location.search);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start YouTube connection.");
      setIsBusy(false);
    }
  };

  const handlePublish = async () => {
    setIsBusy(true);
    setError(null);
    try {
      const published = await publishClipToYouTube(taskId, clipId, {
        title,
        description,
        tags,
        privacy_status: privacy,
      });
      setResult(published);
      toast.success("Clip uploaded to YouTube");
    } catch (err) {
      setError(err instanceof Error ? err.message : "YouTube upload failed.");
    } finally {
      setIsBusy(false);
    }
  };

  const canPublish = status?.connected && !result;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!isBusy) onOpenChange(next); }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Youtube className="w-5 h-5 text-red-600" />
            Publish to YouTube Shorts
          </DialogTitle>
          <DialogDescription>
            Uploads this clip to your connected channel. &quot;#Shorts&quot; is added to the title automatically.
          </DialogDescription>
        </DialogHeader>

        {!status && !error && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking your YouTube connection…
          </div>
        )}

        {status && !status.configured && (
          <p className="text-sm text-gray-600">
            YouTube publishing isn&apos;t enabled on this server. Ask the admin to set <code>COMPOSIO_API_KEY</code>.
          </p>
        )}

        {status?.configured && !status.connected && (
          <p className="text-sm text-gray-600">
            Connect your YouTube channel first. You&apos;ll sign in with Google and come right back here.
          </p>
        )}

        {canPublish && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="yt-title">Title</Label>
              <Input id="yt-title" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="yt-description">Description</Label>
              <Textarea
                id="yt-description"
                rows={3}
                maxLength={5000}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="yt-tags">Tags</Label>
              <Input id="yt-tags" placeholder="podcast, ai, tips" value={tags} onChange={(e) => setTags(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Visibility</Label>
              <Select value={privacy} onValueChange={setPrivacy}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="private">Private</SelectItem>
                  <SelectItem value="unlisted">Unlisted</SelectItem>
                  <SelectItem value="public">Public</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {result && (
          <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            Uploaded as {result.privacy_status}.{" "}
            {result.url && (
              <a href={result.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline">
                Open on YouTube <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <DialogFooter>
          {status?.configured && !status.connected && (
            <Button onClick={handleConnect} disabled={isBusy}>
              {isBusy && <Loader2 className="w-4 h-4 animate-spin" />}
              Connect YouTube
            </Button>
          )}
          {canPublish && (
            <Button onClick={handlePublish} disabled={isBusy || !title.trim()}>
              {isBusy && <Loader2 className="w-4 h-4 animate-spin" />}
              {isBusy ? "Uploading…" : "Publish"}
            </Button>
          )}
          {result && <Button variant="outline" onClick={() => onOpenChange(false)}>Done</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
