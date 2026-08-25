import { NativeModules } from 'react-native';

const { ChurchFinanceNative } = NativeModules;

export interface NativeCppModule {
  reverseString(input: string): Promise<string>;
  computePercentage(contributed: number, allocation: number): Promise<number>;
  formatKES(amount: number): Promise<string>;
}

export const NativeCpp: NativeCppModule = {
  reverseString: (input: string) => ChurchFinanceNative.reverseString(input),
  computePercentage: (contributed: number, allocation: number) =>
    ChurchFinanceNative.computePercentage(contributed, allocation),
  formatKES: (amount: number) => ChurchFinanceNative.formatKES(amount),
};