"use client";

import Hls from "hls.js";
import { useEffect, useMemo, useRef } from "react";

type StreamPlayerProps = {
  defaultUrl: string;
};

export default function StreamPlayer({ defaultUrl }: StreamPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamUrl = defaultUrl;
  const { isMjpeg, isHls } = useMemo(() => {
    const lowerUrl = streamUrl.toLowerCase();
    const isMjpegMatch =
      lowerUrl.includes(".mjpg") || lowerUrl.includes("mjpeg");
    const isHlsMatch = lowerUrl.includes(".m3u8") || lowerUrl.includes("m3u8");
    return { isMjpeg: isMjpegMatch, isHls: isHlsMatch };
  }, [streamUrl]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (!streamUrl) {
      video.removeAttribute("src");
      video.load();
      return;
    }

    if (isMjpeg) {
      video.removeAttribute("src");
      video.load();
      return;
    }

    let hls: Hls | null = null;
    if (isHls && Hls.isSupported()) {
      hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 20,
      });
      hls.loadSource(streamUrl);
      hls.attachMedia(video);
    } else if (isHls && video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = streamUrl;
    } else {
      video.src = streamUrl;
      video.load();
    }

    return () => {
      if (hls) {
        hls.destroy();
      }
    };
  }, [streamUrl, isMjpeg, isHls]);

  return (
    <div className="stream-block">
      <div className="video-shell">
        {streamUrl ? (
          isMjpeg ? (
            <img src={streamUrl} alt="TinyML Stream" />
          ) : (
            <video ref={videoRef} controls autoPlay muted playsInline />
          )
        ) : (
          <div className="video-placeholder">
            <div>
              <strong>No stream URL configured</strong>
              <p>Set NEXT_PUBLIC_STREAM_URL to enable the live feed.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
