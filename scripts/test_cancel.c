/*
 * 测试浮点数相消（Catastrophic Cancellation）
 * 
 * 场景：两个相近的大数相减，有效数字大量丢失
 * 
 * 编译：
 *   gcc -o test_cancel test_cancel.c -lm -g
 * 
 * 运行：
 *   ./test_cancel
 * 
 * Valgrind 检测：
 *   valgrind --tool=exp-float --xml=yes --xml-file=valgrind_report.xml ./test_cancel
 */

#include <stdio.h>
#include <math.h>
#include <stdlib.h>

// 1. 经典相消：两个相近数相减
double catastrophic_cancellation() {
    double a = 1.234567890123456;
    double b = 1.234567890123455;
    double c = a - b;  // 有效数字丢失：15位有效数字 → 1位
    return c;
}

// 2. 二次方程求根（相消的经典案例）
double quadratic_root_cancellation(double a, double b, double c) {
    // 使用有相消风险的公式：x = (-b + sqrt(b*b - 4*a*c)) / (2*a)
    // 当 b >> 4ac 时，-b + sqrt(b^2-4ac) 发生相消
    double discriminant = b * b - 4.0 * a * c;
    double sqrt_disc = sqrt(discriminant);
    double x1 = (-b + sqrt_disc) / (2.0 * a);  // 这里可能发生相消
    return x1;
}

// 3. 差分近似导数（相消）
double finite_difference_derivative(double (*f)(double), double x, double h) {
    // (f(x+h) - f(x)) / h 当 h 很小时发生相消
    return (f(x + h) - f(x)) / h;
}

double my_func(double x) {
    return sin(x) * cos(x);
}

// 4. 安全计算：使用 Kahan 求和
double kahan_sum(const double* data, int n) {
    double sum = 0.0;
    double compensation = 0.0;
    for (int i = 0; i < n; i++) {
        double y = data[i] - compensation;
        double t = sum + y;
        compensation = (t - sum) - y;
        sum = t;
    }
    return sum;
}

// 5. 普通求和（无补偿，存在累积误差）
double naive_sum(const double* data, int n) {
    double sum = 0.0;
    for (int i = 0; i < n; i++) {
        sum += data[i];
    }
    return sum;
}

int main() {
    printf("=== 浮点数相消测试 ===\n\n");

    // 测试 1: 经典相消
    double c1 = catastrophic_cancellation();
    printf("1. 经典相消: 1.234567890123456 - 1.234567890123455 = %.16f\n", c1);
    printf("   预期: ~1e-15, 实际: %.16f\n", c1);
    printf("   有效数字损失: 约 14 位\n\n");

    // 测试 2: 二次方程求根（b >> 4ac 时相消）
    double x = quadratic_root_cancellation(1.0, 1000000.0, 1.0);
    printf("2. 二次方程求根: x^2 + 1e6*x + 1 = 0\n");
    printf("   近似根: x ≈ %.10f\n", x);
    printf("   真解: x ≈ %.10f\n", (-1000000.0 + sqrt(1000000.0*1000000.0 - 4.0)) / 2.0);
    printf("   误差: %.10f\n\n", fabs(x - (-1000000.0 + sqrt(1000000.0*1000000.0 - 4.0)) / 2.0));

    // 测试 3: 差分近似导数（h 很小时相消）
    double h = 1e-12;
    double deriv = finite_difference_derivative(my_func, 1.0, h);
    double exact_deriv = cos(2.0 * 1.0);  // d/dx(sin(x)*cos(x)) = cos(2x) at x=1
    printf("3. 差分近似导数 h=1e-12:\n");
    printf("   近似: %.10f, 精确: %.10f\n", deriv, exact_deriv);
    printf("   误差: %.10f\n\n", fabs(deriv - exact_deriv));

    // 测试 4: Kahan 求和 vs 普通求和
    int n = 100000;
    double* data = (double*)malloc(n * sizeof(double));
    for (int i = 0; i < n; i++) {
        data[i] = 1.0 / (i + 1.0);  // 递减序列
    }
    
    double ks = kahan_sum(data, n);
    double ns = naive_sum(data, n);
    printf("4. 求和对比 (n=%d):\n", n);
    printf("   Kahan 求和: %.15f\n", ks);
    printf("   普通求和:   %.15f\n", ns);
    printf("   差异:       %.15f\n\n", fabs(ks - ns));
    
    free(data);

    // 测试 5: 大量重复相消
    double sum = 0.0;
    for (int i = 0; i < 1000; i++) {
        double a = 1.000000000001 * (i + 1);
        double b = 1.000000000000 * (i + 1);
        sum += a - b;  // 每步都产生相消
    }
    printf("5. 重复相消 1000 次求和: %.16f\n", sum);

    printf("\n=== 测试完成 ===\n");
    return 0;
}
