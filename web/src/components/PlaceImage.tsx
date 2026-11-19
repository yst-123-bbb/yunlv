import { useEffect, useState } from "react";
import { cityInitial, cityTheme } from "../theme/palette";

export default function PlaceImage({
  src,
  name,
  city,
  className = "",
  ratio = "16 / 10",
}: {
  src?: string;
  name: string;
  city?: string;
  className?: string;
  ratio?: string;
}) {
  const [failed, setFailed] = useState(false);

  // A new place may well have a working image, so a previous failure must not stick.
  useEffect(() => {
    setFailed(false);
  }, [name]);

  const theme = cityTheme(city || name);

  return (
    <div className={"placeImage " + className} style={{ aspectRatio: ratio }}>
      {src && !failed ? (
        <img src={src} alt={name} loading="lazy" onError={() => setFailed(true)} />
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