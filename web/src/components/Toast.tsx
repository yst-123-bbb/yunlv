import { useEffect } from "react";

const TONE_CLASS: Record<"info" | "success" | "error", string> = {
  info: "toastInfo",
  success: "toastSuccess",
  error: "toastError",
};

export default function Toast({
  message,
  onClose,
  tone = "info",
}: {
  message: string;
  onClose: () => void;
  tone?: "info" | "success" | "error";
}) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(onClose, 2500);
    return () => clearTimeout(timer);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <div className={"toast " + TONE_CLASS[tone]} role="status">
      {message}
    </div>
  );
}