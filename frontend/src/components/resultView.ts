import { IS_CLASSROOM_APP } from "../appMode";
import { locale } from "../i18n";
import type { Submission } from "../types";

export function isStudentView(submission: Submission): boolean {
  return submission.viewer_role === "author" && !!submission.in_class && !!submission.can_object;
}

export function isClassView(submission: Submission): boolean {
  return IS_CLASSROOM_APP || !!submission.in_class;
}

export function canAnswerObjection(submission: Submission, isStaff: boolean): boolean {
  return submission.viewer_role === "supervisor" || (isStaff && submission.viewer_role !== "author");
}

export function longDate(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleDateString(locale(), { day: "numeric", month: "long", year: "numeric" }) : "";
}

export function isImage(submission: Submission): boolean {
  return !!submission.mime_type?.startsWith("image/");
}
