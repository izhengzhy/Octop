import baiduNetdisk from "./baidu-netdisk.png";
import figma from "./figma.png";
import notion from "./notion.png";
import qqMail from "./qq-mail.png";
import tencentDocs from "./tencent-docs.png";
import tencentIma from "./tencent-ima.png";
import tencentMeeting from "./tencent-meeting.png";
import tencentNews from "./tencent-news.png";
import tencentLexiang from "./tencent-lexiang.png";
import tencentWeiyun from "./tencent-weiyun.png";
import wechatReading from "./wechat-reading.png";
import youdaoNote from "./youdao-note.png";

export const CONNECTOR_LOGOS: Record<string, string> = {
  "tencent-docs": tencentDocs,
  "baidu-netdisk": baiduNetdisk,
  "qq-mail": qqMail,
  "tencent-ima": tencentIma,
  "tencent-lexiang": tencentLexiang,
  "tencent-meeting": tencentMeeting,
  notion,
  "tencent-news": tencentNews,
  "wechat-reading": wechatReading,
  "youdao-note": youdaoNote,
  "tencent-weiyun": tencentWeiyun,
  figma,
};

export function getConnectorLogo(kind: string): string | undefined {
  return CONNECTOR_LOGOS[kind];
}
