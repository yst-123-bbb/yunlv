import { useEffect, useState } from "react";
import { cityInitial, cityTheme } from "../theme/palette";

type Stage = "local" | "remote" | "none";

export default function PlaceImage({
  src,
  name,
  city,
  className = "",
  ratio = "16 / 10",
  fallbackSrc,
}: {
  src?: string;
  name: string;
  city?: string;
  className?: string;
  ratio?: string;
  fallbackSrc?: string;
}) {
  const [stage, setStage] = useState<Stage>(src ? "local" : "none");

  // A new place may well have a working image, so previous failures must not stick.
  useEffect(() => {
    setStage(src ? "local" : "none");
  }, [name, src]);

  const theme = cityTheme(city || name);
  const current = stage === "local" ? src : stage === "remote" ? fallbackSrc : undefined;

  function onError() {
    if (stage === "local" && fallbackSrc && fallbackSrc !== src) setStage("remote");
    else setStage("none");
  }

  return (
    <div className={"placeImage " + className} style={{ aspectRatio: ratio }}>
      {current ? (
        <img src={current} alt={name} loading="lazy" onError={onError} />
      ) : (
        <div
          className="placeImageFallback"
          style={{ background: "linear-gradient(135deg, " + theme.from + ", " + theme.to + ")" }}
        >
          <span className="placeImageInitial">{cityInitial(name)}</span>
          <span className="placeImageLabel">{name}</span>
        </div>
      )}
    </div>
  );
}