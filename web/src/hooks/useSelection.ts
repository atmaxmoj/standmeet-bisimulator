import { useState } from "react";
import { api } from "@/lib/api";

export function useSelection(table: string, onDeleted: () => void) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = (ids: number[]) => {
    setSelected((prev) => {
      const allSelected = ids.every((id) => prev.has(id));
      return allSelected ? new Set() : new Set(ids);
    });
  };

  const deleteSelected = async () => {
    if (!selected.size) return;
    setDeleting(true);
    try {
      await api.batchDelete(table, [...selected]);
      setSelected(new Set());
      onDeleted();
    } catch (e) {
      console.error(e);
    }
    setDeleting(false);
  };

  return { selected, toggle, toggleAll, deleteSelected, deleting };
}
