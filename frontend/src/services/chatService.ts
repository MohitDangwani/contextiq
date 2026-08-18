import { post } from "./httpClient";
import type { ChatResponse } from "../types/api";

export function ask(question: string): Promise<ChatResponse> {
  return post<ChatResponse>("/chat", { question });
}
