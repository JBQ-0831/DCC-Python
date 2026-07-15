import * as vscode from "vscode";

const WIKI_BASE_URL = "https://codeberg.org/nils-soderman/vscode-maya-python/wiki/";

type WikiPages = "Maya-Command-Port";

export function openWikiPage(page: WikiPages) {
    const url = WIKI_BASE_URL + page;
    return vscode.env.openExternal(vscode.Uri.parse(url));
}
