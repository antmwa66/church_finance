package com.churchfinance.app

import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.Promise

class ChurchFinanceNativeModule(reactContext: ReactApplicationContext) : ReactContextBaseJavaModule(reactContext) {

    override fun getName(): String = "ChurchFinanceNative"

    companion object {
        init {
            System.loadLibrary("churchfinance-native")
        }
    }

    external fun nativeReverseString(input: String): String
    external fun nativeComputePercentage(contributed: Double, allocation: Double): Double
    external fun nativeFormatKES(amount: Double): String

    @ReactMethod
    fun reverseString(input: String, promise: Promise) {
        try {
            val result = nativeReverseString(input)
            promise.resolve(result)
        } catch (e: Exception) {
            promise.reject("NATIVE_ERROR", e)
        }
    }

    @ReactMethod
    fun computePercentage(contributed: Double, allocation: Double, promise: Promise) {
        try {
            val result = nativeComputePercentage(contributed, allocation)
            promise.resolve(result)
        } catch (e: Exception) {
            promise.reject("NATIVE_ERROR", e)
        }
    }

    @ReactMethod
    fun formatKES(amount: Double, promise: Promise) {
        try {
            val result = nativeFormatKES(amount)
            promise.resolve(result)
        } catch (e: Exception) {
            promise.reject("NATIVE_ERROR", e)
        }
    }
}