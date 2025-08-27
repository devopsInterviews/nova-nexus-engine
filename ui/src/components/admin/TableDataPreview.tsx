import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface Props {
  tableName: string;
  connectionActive: boolean; // for BI connection path
  internalMode?: boolean; // if true use internal DB endpoints
  pageSize?: number;
  maxHeightClass?: string; // allow parent override
  internalShowAll?: boolean; // if true (default) fetch large batch & hide pagination for internal
}

interface TableRowsResponse {
  columns: string[];
  rows: any[];
  total_rows?: number;
}

// Generic fetch wrapper (localized) – relies on global token
async function fetchRows(table: string, limit: number, offset: number): Promise<TableRowsResponse> {
  const token = localStorage.getItem('auth_token');
  const res = await fetch('/api/get-table-rows', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ table, limit, offset }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.error || 'Failed');
  const payload = data.data || data; // unwrap if wrapped
  return {
    columns: payload.columns || Object.keys(payload.rows?.[0] || {}),
    rows: payload.rows || [],
    total_rows: payload.total_rows,
  };
}

export const TableDataPreview: React.FC<Props> = ({ tableName, connectionActive, internalMode = false, pageSize = 50, maxHeightClass = 'max-h-96', internalShowAll = true }) => {
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<any[]>([]);
  const [page, setPage] = useState(0); // zero-based
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalRows, setTotalRows] = useState<number | null>(null);

  const load = async () => {
    if (!tableName) return;
    setLoading(true); setError(null);
    try {
      if (internalMode) {
        // Internal DB path: optionally fetch whole table (bounded) once
        const token = localStorage.getItem('auth_token');
        const effectiveLimit = internalShowAll ? 5000 : pageSize; // cap to avoid runaway memory
        const offset = internalShowAll ? 0 : page * pageSize;
        const resp = await fetch(`/api/internal/table/${encodeURIComponent(tableName)}?limit=${effectiveLimit}&offset=${offset}`, {
          headers: { 'Authorization': token ? `Bearer ${token}` : '' }
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || data.error || 'Failed');
        const payload = data.data || data;
        setColumns(payload.columns || []);
        setRows(payload.rows || []);
        setTotalRows(typeof payload.total_rows === 'number' ? payload.total_rows : (payload.rows?.length || 0));
      } else {
        if (!connectionActive) {
          setError('No active BI connection');
        } else {
          const offset = page * pageSize;
            const resp = await fetchRows(tableName, pageSize, offset);
            setColumns(resp.columns);
            setRows(resp.rows);
            if (typeof resp.total_rows === 'number') setTotalRows(resp.total_rows);
        }
      }
    } catch (e: any) {
      setError(e.message || 'Error fetching rows');
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setPage(0); // reset when table changes
  }, [tableName]);

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [tableName, page]);

  if (!tableName) return null;
  if (!internalMode && !connectionActive) return <div className="text-sm text-muted-foreground">No active connection.</div>;

  const showPagination = !internalMode || !internalShowAll;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div className="text-sm font-medium">Rows {(page * pageSize) + 1}-{(page * pageSize) + rows.length}{totalRows ? ` / ${totalRows}` : ''}</div>
  {showPagination && (
  <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>Reload</Button>
          <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={loading || page === 0}>Prev</Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setPage(p => (rows.length < pageSize ? p : p + 1))}
            disabled={loading || rows.length < pageSize || (totalRows !== null && (page + 1) * pageSize >= totalRows)}
          >Next</Button>
  </div>)}
      </div>
      {error && (
        <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
      )}
      {loading ? (
        <div className="flex items-center gap-2 text-sm"><div className="animate-spin h-4 w-4 border-b-2 border-primary rounded-full"/> Loading…</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No rows.</div>
      ) : (
        <div className={`${maxHeightClass} overflow-auto border rounded-md`}> 
          <table className="text-sm min-w-full">
            <thead className="bg-muted sticky top-0">
              <tr>{columns.map(c => <th key={c} className="text-left px-2 py-1 font-medium whitespace-nowrap">{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r,i)=>(
                <tr key={i} className="even:bg-muted/40">
                  {columns.map(c => <td key={c} className="px-2 py-1 font-mono text-xs whitespace-nowrap">{String(r[c] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default TableDataPreview;