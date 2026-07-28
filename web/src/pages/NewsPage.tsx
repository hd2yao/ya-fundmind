import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";

export function NewsPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="研究证据"
        title="研究证据"
        description="用于核对基金相关公开信息。该入口只在具备可核验、合规资料后开放。"
      />
      <StatePanel
        kind="empty"
        title="研究证据暂未开放"
        description="当前没有符合正式展示标准的新闻或公告资料。接入可核验且允许展示的公开资料后，此处会提供按基金和主题查看的证据内容。"
      />
    </div>
  );
}
