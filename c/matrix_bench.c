#define _POSIX_C_SOURCE 200809L
/* Сравнение row-major и column-major доступа к матрице uint32_t в C. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <time.h>

static long number(const char *str, long lower, long upper) {
    char *end = NULL;
    errno = 0;
    long n = strtol(str, &end, 10);
    if (errno || !str[0] || !end || *end || n < lower || n > upper) {
        fprintf(stderr, "Invalid number: %s\n", str); exit(2);
    }
    return n;
}
static double seconds(const struct timespec *a, const struct timespec *b) {
    return (double)(b->tv_sec - a->tv_sec) + (double)(b->tv_nsec - a->tv_nsec) / 1e9;
}
static void benchmark(const uint32_t *m, size_t side, int repeat, int columns) {
    volatile uint64_t checksum = 0;
    struct rusage first, last;
    struct timespec start, end;
    if (getrusage(RUSAGE_SELF, &first) || clock_gettime(CLOCK_MONOTONIC, &start)) { perror("start"); exit(1); }
    for (int k = 0; k < repeat; ++k) {
        if (columns) {
            for (size_t col = 0; col < side; ++col)
                for (size_t row = 0; row < side; ++row)
                    checksum += m[row * side + col];
        } else {
            for (size_t row = 0; row < side; ++row)
                for (size_t col = 0; col < side; ++col)
                    checksum += m[row * side + col];
        }
    }
    if (clock_gettime(CLOCK_MONOTONIC, &end) || getrusage(RUSAGE_SELF, &last)) { perror("finish"); exit(1); }
    printf("%s,%zu,%d,%.6f,%ld,%ld,%" PRIu64 "\n", columns ? "column" : "row", side, repeat,
           seconds(&start, &end), last.ru_minflt - first.ru_minflt,
           last.ru_majflt - first.ru_majflt, (uint64_t)checksum);
}
int main(int argc, char **argv) {
    long side = 2048, repeat = 3;
    const char *order = "both";
    for (int i = 1; i < argc; i++) {
        if (i + 1 >= argc) { fprintf(stderr, "Usage: matrix_bench [--size 2048] [--repeats 3] [--order row|column|both]\n"); return 2; }
        const char *flag = argv[i++], *arg = argv[i];
        if (!strcmp(flag, "--size")) side = number(arg, 1, 8192);
        else if (!strcmp(flag, "--repeats")) repeat = number(arg, 1, 20);
        else if (!strcmp(flag, "--order")) order = arg;
        else { fprintf(stderr, "Unknown flag: %s\n", flag); return 2; }
    }
    if (strcmp(order, "row") && strcmp(order, "column") && strcmp(order, "both")) {
        fprintf(stderr, "Invalid traversal order\n"); return 2;
    }
    const size_t n = (size_t)side;
    uint32_t *matrix = malloc(n * n * sizeof *matrix);
    if (!matrix) { perror("malloc matrix"); return 1; }
    for (size_t i = 0; i < n * n; i++) matrix[i] = (uint32_t)(i % 127);
    printf("order,side,repeats,seconds,minor_faults,major_faults,checksum\n");
    if (strcmp(order, "column")) benchmark(matrix, n, (int)repeat, 0);
    if (strcmp(order, "row")) benchmark(matrix, n, (int)repeat, 1);
    free(matrix);
    return 0;
}
