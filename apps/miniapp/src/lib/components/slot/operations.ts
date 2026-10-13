import lineups from './operations.json';
export const multipliers: Record<string,number> = {D1:1,D2:2,D3:3,D4:4,A1:8,A2:10,A3:20,W:50};
export const operations = lineups.ops;
export function knownOperation(value: unknown): value is string {
  return typeof value === 'string' && operations.some(op => op.id === value);
}
export function operatorForSymbol(operationId:string, code:string): string | null {
  const op=operations.find(item=>item.id===operationId);
  if(!op) return null;
  if(code==='W') return lineups.wild;
  if(/^D[1-4]$/.test(code)) return op.def[Number(code[1])-1];
  if(/^A[1-3]$/.test(code)) return op.atk[Number(code[1])-1];
  return null;
}
export function displayOperation(publicState:Record<string,unknown>, hasResult:boolean, spinning:boolean, frozen:string): string {
  const last=publicState.last_result;
  if(hasResult && typeof last==='object' && last!==null && 'operation_id' in last && knownOperation(last.operation_id)) return last.operation_id;
  if(spinning && knownOperation(frozen)) return frozen;
  return knownOperation(publicState.operation_id) ? publicState.operation_id : 'op1';
}
