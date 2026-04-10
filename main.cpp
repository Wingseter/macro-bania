#include <array>
#include <algorithm>
#include <cstdio>

int main() {
    std::array<int, 9> numbers = {5, 3, 8, 1, 9, 2, 7, 4, 6};

    std::puts("Before sorting:");
    for (const int n : numbers) {
        std::printf("%d ", n);
    }
    std::putchar('\n');

    std::sort(numbers.begin(), numbers.end());

    std::puts("After sorting:");
    for (const int n : numbers) {
        std::printf("%d ", n);
    }
    std::putchar('\n');
}
