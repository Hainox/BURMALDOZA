export type ConnectionStatus = 'demo' | 'connecting' | 'connected' | 'syncing' | 'offline';

export class SessionState {
  balance = $state(1250);
  currencyCode = $state('JOKERGEM');
  connection = $state<ConnectionStatus>('demo');
  reducedMotion = $state(false);
  displayName = $state('Гость');

  setReducedMotion(value: boolean) {
    this.reducedMotion = value;
  }

  setConnection(value: ConnectionStatus) {
    this.connection = value;
  }

  setBalance(balance: number, currencyCode = this.currencyCode) {
    this.balance = balance;
    this.currencyCode = currencyCode;
  }
}
