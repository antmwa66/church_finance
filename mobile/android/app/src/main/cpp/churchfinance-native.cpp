#include <jni.h>
#include <string>
#include <cmath>

extern "C" {

JNIEXPORT jstring JNICALL
Java_com_churchfinance_app_ChurchFinanceNativeModule_nativeReverseString(
        JNIEnv* env,
        jobject /* this */,
        jstring input) {
    const char* chars = env->GetStringUTFChars(input, nullptr);
    std::string str(chars);
    env->ReleaseStringUTFChars(input, chars);

    std::reverse(str.begin(), str.end());
    return env->NewStringUTF(str.c_str());
}

JNIEXPORT jdouble JNICALL
Java_com_churchfinance_app_ChurchFinanceNativeModule_nativeComputePercentage(
        JNIEnv* env,
        jobject /* this */,
        jdouble contributed,
        jdouble allocation) {
    if (allocation <= 0.0) return 0.0;
    double percentage = (contributed / allocation) * 100.0;
    return std::round(percentage * 100.0) / 100.0;
}

JNIEXPORT jstring JNICALL
Java_com_churchfinance_app_ChurchFinanceNativeModule_nativeFormatKES(
        JNIEnv* env,
        jobject /* this */,
        jdouble amount) {
    char buffer[64];
    snprintf(buffer, sizeof(buffer), "KES %.2f", amount);
    return env->NewStringUTF(buffer);
}

}