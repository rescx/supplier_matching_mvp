type Props = { status: string };

const colors: Record<string, string> = {
  UNMAPPED: "badge unmapped",
  PENDING: "badge pending",
  APPROVED: "badge approved",
  REJECTED: "badge rejected",
};

export default function StatusBadge({ status }: Props) {
  const cls = colors[status] || colors.UNMAPPED;
  return <span className={cls}>{status}</span>;
}
