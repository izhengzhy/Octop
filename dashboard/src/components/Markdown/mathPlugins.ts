import { useEffect, useState } from "react";
import type { PluggableList } from "unified";

const MATH_PATTERN =
  /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|(?:^|[^\w$\\])\$[^\n$]+\$(?:$|[^\w$])/m;

export function contentHasMath(content: string): boolean {
  return MATH_PATTERN.test(content);
}

let katexCssLoaded = false;

export function ensureKatexCss() {
  if (katexCssLoaded || typeof document === "undefined") return;
  katexCssLoaded = true;
  void import("katex/dist/katex.min.css");
}

type MathPlugins = {
  remarkPlugins: PluggableList;
  rehypePlugins: PluggableList;
};

export function useMathPlugins(content: string): MathPlugins {
  const hasMath = contentHasMath(content);
  const [plugins, setPlugins] = useState<MathPlugins>({
    remarkPlugins: [],
    rehypePlugins: [],
  });

  useEffect(() => {
    if (!hasMath) {
      setPlugins({ remarkPlugins: [], rehypePlugins: [] });
      return;
    }

    let cancelled = false;
    void (async () => {
      const [{ default: remarkMath }, { default: rehypeKatex }] =
        await Promise.all([import("remark-math"), import("rehype-katex")]);
      ensureKatexCss();
      if (!cancelled) {
        setPlugins({
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [hasMath, content]);

  return plugins;
}
