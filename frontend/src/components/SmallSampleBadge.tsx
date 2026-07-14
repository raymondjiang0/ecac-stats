interface Props { n: number }

export default function SmallSampleBadge({ n }: Props) {
  return (
    <span className="badge badge-sample" title="Fewer than 5 games — interpret with caution">
      Small Sample · n={n}
    </span>
  )
}
