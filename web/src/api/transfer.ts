import { apiGet } from "./client";

export interface TransferLeg {
  mode: "train" | "flight";
  from: string;
  to: string;
  price: number;
  duration_min: number;
}

export interface TransferOption {
  via: string;
  via_province: string;
  total: number;
  save: number;
  duration_min: number;
  summary: string;
  legs: TransferLeg[];
}

export interface TransferResult {
  origin: string;
  dest: string;
  people: number;
  direct: { total: number; duration_min: number };
  options: TransferOption[];
  best: TransferOption | null;
  note: string;
}

export async function fetchTransfers(origin: string, dest: string, people = 1): Promise<TransferResult> {
  return apiGet<TransferResult>(
    `/api/transport/transfers?origin=${encodeURIComponent(origin)}&dest=${encodeURIComponent(dest)}&people=${people}`,
  );
}