import {expect,it} from 'vitest';
import {displayOperation,operatorForSymbol,operations} from './operations';
it('maps only confirmed symbol codes and keeps Tachanka in every operation',()=>{
  expect(operatorForSymbol('op1','D1')).toBe('Pulse');
  expect(operatorForSymbol('op2','D1')).toBe('Kaid');
  for(const op of operations)expect(operatorForSymbol(op.id,'W')).toBe('Tachanka');
  for(const symbol of ['A','B','C','D5','A4','?'])expect(operatorForSymbol('op1',symbol)).toBeNull();
});
it('freezes faces for the spin/result, then accepts the next snapshot operation',()=>{
  const snapshot={operation_id:'op2',last_result:{operation_id:'op1'}};
  expect(displayOperation(snapshot,true,false,'op1')).toBe('op1');
  expect(displayOperation(snapshot,false,true,'op1')).toBe('op1');
  expect(displayOperation(snapshot,false,false,'op1')).toBe('op2');
  expect(displayOperation({},false,false,'op1')).toBe('op1');
});
