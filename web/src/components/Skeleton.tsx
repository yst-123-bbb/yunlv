export default function Skeleton({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={"skeletonBox " + className}>
      {Array.from({ length: Math.max(0, lines) }, (_, i) => (
        <div className="skeletonLine" key={i} />
      ))}
    </div>
  );
}