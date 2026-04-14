#!/usr/bin/env bash
# collect_knowledge.sh
# Clones LibGDX documentation and source code into the knowledge/ directory.
# Run from the project root: bash scripts/collect_knowledge.sh

set -euo pipefail

KNOWLEDGE_DIR="knowledge"
TMP_DIR="scripts/.tmp"

mkdir -p "$KNOWLEDGE_DIR" "$TMP_DIR"

# ─── 1. LibGDX Wiki (Markdown docs) ──────────────────────────────────────────
echo "📚 Fetching LibGDX wiki docs..."
WIKI_REPO="$TMP_DIR/libgdx.github.io"
if [ ! -d "$WIKI_REPO" ]; then
    git clone --depth 1 https://github.com/libgdx/libgdx.github.io.git "$WIKI_REPO"
fi

WIKI_TARGET="$KNOWLEDGE_DIR/libgdx-wiki"
rm -rf "$WIKI_TARGET"
mkdir -p "$WIKI_TARGET"

# Copy all markdown files from the wiki directory
if [ -d "$WIKI_REPO/wiki" ]; then
    cp -r "$WIKI_REPO/wiki/"* "$WIKI_TARGET/"
else
    # Fallback: grab all .md files from the repo
    find "$WIKI_REPO" -name "*.md" -not -path "*/.git/*" -exec cp {} "$WIKI_TARGET/" \;
fi

WIKI_COUNT=$(find "$WIKI_TARGET" -type f | wc -l | tr -d ' ')
echo "   ✅ Wiki: $WIKI_COUNT files"

# ─── 2. LibGDX Source (key Java files) ───────────────────────────────────────
echo "🔧 Fetching LibGDX source code..."
SRC_REPO="$TMP_DIR/libgdx"
if [ ! -d "$SRC_REPO" ]; then
    git clone --depth 1 --filter=blob:none --sparse https://github.com/libgdx/libgdx.git "$SRC_REPO"
    pushd "$SRC_REPO" > /dev/null
    git sparse-checkout set gdx/src extensions
    popd > /dev/null
fi

SRC_TARGET="$KNOWLEDGE_DIR/libgdx-src"
rm -rf "$SRC_TARGET"
mkdir -p "$SRC_TARGET"

# Copy only .java files to keep it focused
find "$SRC_REPO/gdx/src" "$SRC_REPO/extensions" -name "*.java" 2>/dev/null | while read -r f; do
    # Preserve relative path structure
    rel="${f#$SRC_REPO/}"
    mkdir -p "$SRC_TARGET/$(dirname "$rel")"
    cp "$f" "$SRC_TARGET/$rel"
done

SRC_COUNT=$(find "$SRC_TARGET" -name "*.java" -type f | wc -l | tr -d ' ')
echo "   ✅ Source: $SRC_COUNT Java files"

# ─── 3. LibGDX Demo Projects ────────────────────────────────────────────────
echo "🎮 Fetching LibGDX demo projects..."
DEMO_REPO="$TMP_DIR/libgdx-demo-superjumper"
if [ ! -d "$DEMO_REPO" ]; then
    git clone --depth 1 https://github.com/libgdx/libgdx-demo-superjumper.git "$DEMO_REPO"
fi

DEMO_TARGET="$KNOWLEDGE_DIR/libgdx-demos"
rm -rf "$DEMO_TARGET"
mkdir -p "$DEMO_TARGET"

# Copy Java and resource files
find "$DEMO_REPO" \( -name "*.java" -o -name "*.md" -o -name "*.txt" \) -not -path "*/.git/*" | while read -r f; do
    rel="${f#$DEMO_REPO/}"
    mkdir -p "$DEMO_TARGET/$(dirname "$rel")"
    cp "$f" "$DEMO_TARGET/$rel"
done

DEMO_COUNT=$(find "$DEMO_TARGET" -type f | wc -l | tr -d ' ')
echo "   ✅ Demos: $DEMO_COUNT files"

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────"
TOTAL=$(find "$KNOWLEDGE_DIR" -type f | wc -l | tr -d ' ')
echo "📦 Total knowledge files: $TOTAL"
echo "📂 Location: $KNOWLEDGE_DIR/"
du -sh "$KNOWLEDGE_DIR" | awk '{print "💾 Size: " $1}'
echo "─────────────────────────────────────"
echo ""
echo "✅ Knowledge base ready. Run ingestion next:"
echo "   docker compose run rag python ingest.py"
